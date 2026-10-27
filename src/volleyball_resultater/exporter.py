from __future__ import annotations

import argparse
from datetime import datetime, time
import json
from pathlib import Path
import sqlite3

import pandas as pd

from . import __version__
from .paths import DEFAULT_DB_PATH, DEFAULT_EXPORT_DIR
from .wrangling import calculate_running_points, result_matrix


def export_json(db_path: Path, output_dir: Path) -> None:
    """Read a consistent database snapshot and write frontend-compatible JSON."""
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("BEGIN")
        pools = pd.read_sql(
            sql="""
                SELECT 
                    x.*,
                    y.league_name,
                    y.district,
                    y.gender,
                    y.season,
                    y.age_group
                FROM pools x 
                JOIN leagues y
                ON x.league_id=y.league_id
                ORDER BY x.league_id, x.pool_name, x.pool_id
            """,
            con=connection,
            dtype_backend="numpy_nullable"
        )

        rankings = pd.read_sql("SELECT * FROM rankings ORDER BY pool_id, rank, team_name",
                               connection, dtype_backend="numpy_nullable")
        matches = pd.read_sql(
            "SELECT * FROM matches ORDER BY pool_id, match_time IS NULL, match_time, match_number, match_id",
            connection, dtype_backend="numpy_nullable",
        )
    finally:
        connection.close()

    # Keep prefixed identifiers throughout calculations; map frontend names at export.
    score_columns = matches.columns[matches.columns.str.contains(r"_(?:sets|points|balls\d+)$")]
    # SQL cannot infer numeric dtypes from a column containing only NULL values.
    matches[score_columns] = matches[score_columns].astype("Int64")
    matches["match_time"] = pd.to_datetime(matches["match_time"])
    matches["note"] = matches["note"].fillna("").replace(r"(?i)^\s*(nan|<na>)\s*$", "", regex=True)
    leagues = pools[['league_id', 'league_name', 'district', 'gender', 'age_group', 'season']].drop_duplicates(
        ignore_index=True
    ).sort_values(['season', 'gender', 'league_name', 'league_id'], ascending=[False, True, True, True])
    metadata = {
        "schema_version": 1, "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scraper_version": __version__, "point_source": "scraped_tournament_points",
    }
    payloads = []
    pool_validation = {}
    for pool_id in pools["pool_id"]:
        pool_rankings = rankings.loc[rankings["pool_id"].eq(pool_id)]
        pool_matches = matches.loc[matches["pool_id"].eq(pool_id)]

        events, matrix = derive_pool(pool_matches)
        
        validation = compare_standings(pool_rankings, events)
        if not validation:
            pool_validation[str(pool_id)] = validation

        # Rename fields and convert to records only at the frontend boundary.
        payloads.append((str(pool_id), {
            "metadata": {**metadata, "validation": "points" in validation["affected_fields"]},
            "pool": records(frontend_pools(pools.loc[pools["pool_id"].eq(pool_id)]))[0],
            "source_standings": records(pool_rankings.assign(pool_id=str(pool_id))),
            "matches": records(frontend_matches(pool_matches)),
            "cumulative_points": records(events),
            "result_matrix": matrix.astype(object).where(matrix.notna(), None).to_dict(orient="index"),
        }))
    index = {
        "metadata": {**metadata, "seasons": sorted(leagues["season"].astype(str).unique(), reverse=True),
                     "league_count": len(leagues), "pool_count": len(pools),
                     "validation": {"pools_with_mismatches": len(pool_validation),
                                    "mismatch_count": len(pool_validation)}},
        "leagues": records(frontend_leagues(leagues)), "pools": records(frontend_pools(pools)),
        "pool_validation": pool_validation,
    }
    # Read and merge before writing any files: an unreadable index must not lose history.
    index = merge_index(output_dir / "leagues.json", index)
    output_dir.mkdir(parents=True, exist_ok=True)
    for pool_id, payload in payloads:
        write_json(output_dir / f"{safe_filename(pool_id)}.json", payload)
    write_json(output_dir / "leagues.json", index)


def merge_entries(previous: list[dict], current: list[dict], source_id: str,
                  seasonal: bool = False) -> tuple[list[dict], dict[str, str]]:
    """Prefer current entries, matching both JSON IDs and legacy source IDs."""
    entries = previous + current
    frame = pd.DataFrame(entries)
    if frame.empty:
        return [], {}
    frame["id"] = frame["id"].astype(str)
    frame = frame.drop_duplicates("id", keep="last")
    frame["_identity"] = "id:" + frame["id"]
    if source_id in frame:
        source = pd.to_numeric(frame[source_id]).astype("Int64").astype("string")
        identity = "source:" + source
        if seasonal:
            identity = frame["season_id"].astype(str) + ":" + identity
        frame["_identity"] = identity.fillna(frame["_identity"])
    merged = frame.drop_duplicates("_identity", keep="last")
    aliases = frame.set_index("id")["_identity"].map(merged.set_index("_identity")["id"]).to_dict()
    # Keep each selected JSON record's original fields; dataframe alignment would
    # otherwise add null fields to historical records that never contained them.
    return [{**entries[position], "id": str(entries[position]["id"])} for position in merged.index], aliases


def merge_index(path: Path, current: dict) -> dict:
    """Retain unexported seasons and validation; refresh entries present in this run."""
    if not path.exists():
        return current
    previous = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(previous, dict) or not all(
        isinstance(previous.get(key), list) for key in ("leagues", "pools")
    ):
        raise ValueError(f"Cannot merge invalid index: {path}")
    leagues, league_aliases = merge_entries(previous["leagues"], current["leagues"], "raekke_id", seasonal=True)
    pools, pool_aliases = merge_entries(previous["pools"], current["pools"], "pulje_id")
    pools = [{**pool, "league_id": league_aliases.get(str(pool["league_id"]), str(pool["league_id"]))}
             for pool in pools]
    refreshed = {str(pool["id"]) for pool in current["pools"]}
    validation = {
        pool_aliases.get(str(pool_id), str(pool_id)): summary
        for pool_id, summary in previous.get("pool_validation", {}).items()
        if pool_aliases.get(str(pool_id), str(pool_id)) not in refreshed and summary["mismatch_count"] > 0
    }
    validation.update(current["pool_validation"])
    return {
        **previous, **current,
        "leagues": leagues, "pools": pools, "pool_validation": validation,
        "metadata": {
            **previous.get("metadata", {}), **current["metadata"],
            "seasons": sorted({str(league["season_id"]) for league in leagues}, reverse=True),
            "league_count": len(leagues), "pool_count": len(pools),
            "validation": {
                "pools_with_mismatches": len(validation),
                "mismatch_count": sum(summary["mismatch_count"] for summary in validation.values()),
            },
        },
    }


def frontend_leagues(leagues: pd.DataFrame) -> pd.DataFrame:
    return leagues.rename(columns={"league_id": "id", "league_name": "name", "season": "season_id"}).assign(
        raekke_id=leagues["league_id"], id=leagues["league_id"].astype(str), season_id=leagues["season"].astype(str),
        division=leagues["league_name"].str.replace(r"(?i)\s+(Herrer|Kvinder)$", "", regex=True).str.strip(),
    )


def frontend_pools(pools: pd.DataFrame) -> pd.DataFrame:
    return pools.rename(columns={"pool_id": "id", "pool_name": "name", "season": "season_id"}).assign(
        pulje_id=pools["pool_id"], id=pools["pool_id"].astype(str), league_id=pools["league_id"].astype(str),
        raekke_id=pools["league_id"], season_id=pools["season"].astype(str),
        season_value=pools["season"].astype(str), season_start_year=pools["season"],
        division=pools["league_name"].str.replace(r"(?i)\s+(Herrer|Kvinder)$", "", regex=True).str.strip(),
    )


def frontend_matches(matches: pd.DataFrame) -> pd.DataFrame:
    # The original columns stay in SQLite; JSON only carries their frontend names.
    return matches.rename(columns={
        "match_id": "kamp_id", "match_time": "starts_at", "home_sets": "result_home_sets",
        "away_sets": "result_away_sets", "note": "result_note",
    }).assign(
        pool_id=matches["pool_id"].astype(str),
        starts_at_time_known=matches["match_time"].notna() & matches["match_time"].dt.time.ne(time(0)),
    )


def records(frame: pd.DataFrame) -> list[dict]:
    """Serialize timestamps and missing values without losing integer IDs."""
    frame = frame.copy()
    for column in frame.select_dtypes(include=["datetime", "datetimetz"]).columns:
        frame[column] = frame[column].map(lambda value: value.isoformat() if pd.notna(value) else None)
    return frame.astype(object).where(frame.notna(), None).to_dict(orient="records")


def derive_pool(matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = calculate_running_points(matches)
    events.rename(columns={"match_time": "date"}, inplace=True)

    matrix = result_matrix(matches).unstack()

    return events, matrix


def compare_standings(rankings: pd.DataFrame, events: pd.DataFrame) -> bool:
    current = events.loc[events.groupby(['team'])['date'].idxmax()]
    compare = rankings.join(current.set_index('team')[['cumulative_points']], on='team_name')
    validation = compare['points'].eq(compare['cumulative_points']).all()

    return validation


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT_DIR)
    args = parser.parse_args()
    export_json(args.db, args.output)

def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)

if __name__ == "__main__":
    main()
