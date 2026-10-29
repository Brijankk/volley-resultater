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
    pools = pool_filter(pools)

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
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scraper_version": __version__,
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
            "metadata": {**metadata, "validation": validation},
            "pool": records(frontend_pools(pools.loc[pools["pool_id"].eq(pool_id)]))[0],
            "source_standings": records(pool_rankings.assign(pool_id=str(pool_id))),
            "matches": records(frontend_matches(pool_matches)),
            "cumulative_points": records(events),
            "result_matrix": matrix.astype(object).where(matrix.notna(), None).to_dict(orient="index"),
        }))
    index = {
        "metadata": {
            **metadata,
            "seasons": sorted(leagues["season"].astype(str).unique(), reverse=True),
            "league_count": len(leagues),
            "pool_count": len(pools)
        },
        "leagues": records(frontend_leagues(leagues)),
        "pools": records(frontend_pools(pools)[['id', 'name', 'league_id']]),
        "pool_validation": pool_validation,
    }
    # Read and merge before writing any files: an unreadable index must not lose history.
    index = merge_index(output_dir / "leagues.json", index)
    output_dir.mkdir(parents=True, exist_ok=True)
    for pool_id, payload in payloads:
        write_json(output_dir / f"{safe_filename(pool_id)}.json", payload)
    write_json(output_dir / "leagues.json", index)


def merge_index(path: Path, current: dict) -> dict:
    """Retain unexported seasons and validation; refresh entries present in this run."""
    if not path.exists():
        return current
    previous = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(previous, dict) or not all(
        isinstance(previous.get(key), list) for key in ("leagues", "pools")
    ):
        raise ValueError(f"Cannot merge invalid index: {path}")

    previous_leagues = pd.DataFrame(previous['leagues'])
    current_leagues = pd.DataFrame(current['leagues'])
    new_leagues = pd.concat(
        objs=[previous_leagues, current_leagues],
        ignore_index=True
    ).drop_duplicates(subset='id', keep='last')

    previous_pools = pd.DataFrame(previous['pools'])
    current_pools = pd.DataFrame(current['pools'])
    new_pools = pd.concat(
        objs=[previous_pools, current_pools],
        ignore_index=True
    ).drop_duplicates(subset='id', keep='last')

    previous_validation = set(previous['pool_validation'].keys())
    current_validation = set(current['pool_validation'].keys())
    new_validation = previous_validation.difference(current_pools['id']) | current_validation
    new_pool_validation = {item: True for item in new_validation}

    new_metadata = current['metadata'].copy()
    new_metadata['seasons'] = sorted(list(set(previous['metadata']['seasons']) | set(current['metadata']['seasons'])), reverse=True)
    new_metadata['league_count'] = new_leagues.shape[0]
    new_metadata['pool_count'] = new_pools.shape[0]

    new_index = {
        'metadata': new_metadata,
        'leagues': new_leagues.to_dict(orient='records'),
        'pools': new_pools.to_dict(orient='records'),
        'pool_validation': new_pool_validation
    }

    return new_index
    

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

def pool_filter(pools: pd.DataFrame) -> pd.DataFrame:
    pools = pools.loc[
        pools['league_name'].str.contains('division', case=False) |
        (
            pools['league_name'].str.contains('volleyligaen', case=False) &
            ~pools['league_name'].str.contains('finale', case=False) &
            ~pools['league_name'].str.contains('bronze', case=False)
        )
    ].copy()

    return pools

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
    current = events.loc[events.groupby(['team'])['game_number'].idxmax()]
    compare = rankings.join(current.set_index('team')[['cumulative_points']], on='team_name')
    validation = bool(compare['points'].eq(compare['cumulative_points']).all())

    return validation


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)

