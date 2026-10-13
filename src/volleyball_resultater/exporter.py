"""Export the new SQLite schema for the frontend using pandas dataframes.

Tournament points come from the scraped matches, not rule profiles.
Run with ``python -m volleyball_resultater.exporter_new``.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time
import json
from pathlib import Path
import sqlite3

import pandas as pd

from . import __version__
from .paths import PROJECT_ROOT


POINT_SOURCE = "source_points"
STAT_FIELDS = [
    "games_played", "games_won", "games_lost", "sets_won", "sets_lost",
    "balls_won", "balls_lost", "points",
]


def export_json(db_path: Path, output_dir: Path) -> None:
    """Read a consistent database snapshot and write frontend-compatible JSON."""
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("BEGIN")
        pools = pd.read_sql(
            sql="""
                SELECT 
                    x.*,
                    y.name as [league_name],
                    y.district,
                    y.gender,
                    y.season,
                    y.age_group
                FROM pools x 
                JOIN leagues y
                ON x.league_id=y.id
                ORDER BY x.league_id, x.name, x.id
            """,
            con=connection,
            dtype_backend="numpy_nullable"
        ).rename(columns={"id": "pool_id", "name": "pool_name"})

        rankings = pd.read_sql("SELECT * FROM rankings ORDER BY pool_id, rank, team_name",
                               connection, dtype_backend="numpy_nullable")
        matches = pd.read_sql(
            "SELECT * FROM matches ORDER BY pool_id, match_time IS NULL, match_time, match_number, id",
            connection, dtype_backend="numpy_nullable",
        ).rename(columns={"id": "match_id"})
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
        sets = set_results(pool_matches)
        computed, events, matrix = derive_pool(pool_id, pool_rankings, pool_matches, sets)
        validation = compare_standings(pool_rankings, computed)
        if validation["mismatch_count"]:
            pool_validation[str(pool_id)] = validation
        # Rename fields and convert to records only at the frontend boundary.
        payloads.append((str(pool_id), {
            "metadata": {**metadata, "rule_profile": POINT_SOURCE, "validation": validation,
                         "ranking_note": "Rank is indicative; validation compares statistics, not tie-break order."},
            "pool": records(frontend_pools(pools.loc[pools["pool_id"].eq(pool_id)]))[0],
            "source_standings": records(pool_rankings.assign(pool_id=str(pool_id))),
            "computed_standings": records(computed.assign(pool_id=str(pool_id))),
            "matches": records(frontend_matches(pool_matches)),
            "set_results": records(sets.rename(columns={"match_id": "kamp_id"})),
            "rule_profile": POINT_SOURCE,
            "cumulative_points": records(events.rename(columns={"match_id": "kamp_id"})),
            "result_matrix": matrix.astype(object).where(matrix.notna(), None).to_dict(orient="index"),
        }))
    index = {
        "metadata": {**metadata, "seasons": sorted(leagues["season"].astype(str).unique(), reverse=True),
                     "league_count": len(leagues), "pool_count": len(pools),
                     "validation": {"pools_with_mismatches": len(pool_validation),
                                    "mismatch_count": sum(v["mismatch_count"] for v in pool_validation.values())}},
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


def set_results(matches: pd.DataFrame) -> pd.DataFrame:
    columns = ["match_id", "set_number", "home_points", "away_points", "home_set_won", "away_set_won"]
    if matches.empty:
        return pd.DataFrame(columns=columns)
    sets = pd.wide_to_long(
        df=matches[matches.columns[matches.columns.str.contains('match_id|balls')]],
        stubnames=["home_balls", "away_balls"],
        i="match_id",
        j="set_number",
    ).reset_index().rename(columns={"home_balls": "home_points", "away_balls": "away_points"})
    sets = sets.dropna(subset=["home_points", "away_points"], how="all")
    known = sets[["home_points", "away_points"]].notna().all(axis=1)
    sets["home_set_won"] = sets["home_points"].gt(sets["away_points"]).astype("Int64").where(known)
    sets["away_set_won"] = sets["away_points"].gt(sets["home_points"]).astype("Int64").where(known)
    return sets[columns].sort_values(["match_id", "set_number"])


def derive_pool(pool_id: int, rankings: pd.DataFrame, matches: pd.DataFrame,
                sets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    teams = pd.Index(sorted(pd.concat([rankings["team_name"], matches["home_team"],
                                      matches["away_team"]]).dropna().unique()), name="team_name")
    played = matches.loc[matches[["home_sets", "away_sets"]].notna().all(axis=1)
                         & matches["home_sets"].ne(matches["away_sets"])].copy()
    played["match_order"] = range(len(played))
    balls = sets.dropna(subset=["home_points", "away_points"]).groupby("match_id")[["home_points", "away_points"]].sum()
    balls = balls.reindex(played["match_id"], fill_value=0)
    # Retain the administrative 25-0 convention when a forfeit has no set details.
    forfeits = played.loc[played["note"].str.contains("HHT|UHT", case=False)
                         & ~played["match_id"].isin(sets["match_id"])]
    home_won = forfeits["home_sets"].gt(forfeits["away_sets"])
    awarded_balls = forfeits[["home_sets", "away_sets"]].max(axis=1) * 25
    balls.loc[forfeits["match_id"], "home_points"] = awarded_balls.where(home_won, 0).to_numpy()
    balls.loc[forfeits["match_id"], "away_points"] = awarded_balls.where(~home_won, 0).to_numpy()
    sides = []
    for side_number, (side, opponent) in enumerate((("home", "away"), ("away", "home"))):
        team_matches = played[["match_id", "match_time", "match_order", f"{side}_team", f"{side}_points",
                               f"{side}_sets", f"{opponent}_sets"]].rename(columns={
            f"{side}_team": "team_name", f"{side}_points": "points",
            f"{side}_sets": "sets_won", f"{opponent}_sets": "sets_lost",
        })
        sides.append(team_matches.assign(
            side_order=side_number, games_played=1,
            games_won=team_matches["sets_won"].gt(team_matches["sets_lost"]).astype(int),
            games_lost=team_matches["sets_won"].lt(team_matches["sets_lost"]).astype(int),
            balls_won=team_matches["match_id"].map(balls[f"{side}_points"]),
            balls_lost=team_matches["match_id"].map(balls[f"{opponent}_points"]),
        ))
    team_matches = pd.concat(sides, ignore_index=True).sort_values(["match_order", "side_order"])
    team_matches[STAT_FIELDS] = team_matches[STAT_FIELDS].astype("Int64")
    grouped = team_matches.groupby("team_name", sort=False)
    stats = grouped[STAT_FIELDS].sum().reindex(teams, fill_value=0)
    # Missing scraped points make the total unknown; do not infer an award.
    incomplete = grouped["points"].count().lt(grouped.size())
    stats.loc[incomplete.index[incomplete], "points"] = pd.NA
    computed = stats.reset_index().assign(
        set_difference=lambda df: df["sets_won"] - df["sets_lost"],
        ball_difference=lambda df: df["balls_won"] - df["balls_lost"],
        sort_points=lambda df: df["points"].fillna(0),
    ).sort_values(["sort_points", "set_difference", "ball_difference", "team_name"],
                  ascending=[False, False, False, True]).drop(columns=["sort_points", "set_difference", "ball_difference"])
    computed = computed.assign(pool_id=pool_id, rule_profile=POINT_SOURCE, rank=range(1, len(computed) + 1))
    team_matches["game_number"] = grouped.cumcount() + 1
    team_matches["cumulative_points"] = grouped["points"].cumsum(skipna=False)
    baseline = pd.DataFrame({"team": teams, "date": pd.NaT, "game_number": 0,
                             "points": 0, "cumulative_points": 0, "match_id": pd.NA})
    events = pd.concat([baseline, team_matches.rename(columns={
        "team_name": "team", "match_time": "date",
    })[baseline.columns]], ignore_index=True)
    played["score"] = played["home_sets"].astype(str) + "-" + played["away_sets"].astype(str)
    matrix = played.groupby(["home_team", "away_team"])["score"].agg(", ".join).unstack("away_team")
    matrix = matrix.reindex(index=teams, columns=teams)
    diagonal = teams.to_numpy()[:, None] == teams.to_numpy()[None, :]
    matrix = matrix.mask(diagonal, "")
    return computed, events, matrix


def compare_standings(official: pd.DataFrame, computed: pd.DataFrame) -> dict:
    source = official.set_index("team_name")[STAT_FIELDS]
    derived = computed.set_index("team_name")[STAT_FIELDS]
    common = source.index.intersection(derived.index)
    missing = source.index.symmetric_difference(derived.index)
    differences = source.loc[common].ne(derived.loc[common]).fillna(True)
    fields = differences.columns[differences.any()].tolist()
    if len(missing):
        fields.append("team")
    return {"mismatch_count": int(differences.sum().sum()) + len(missing),
            "affected_teams": int(differences.any(axis=1).sum()) + len(missing),
            "affected_fields": sorted(fields), "compared_fields": STAT_FIELDS}


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=PROJECT_ROOT / "data" / "volleyball_new.sqlite")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "json_new")
    args = parser.parse_args()
    export_json(args.db, args.output)

def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)

if __name__ == "__main__":
    main()
