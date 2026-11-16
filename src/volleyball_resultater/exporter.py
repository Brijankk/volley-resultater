from __future__ import annotations

from datetime import datetime, time
import json
from pathlib import Path
import sqlite3

import pandas as pd

from . import __version__
from .storage import Repository
from .wrangling import calculate_running_points, result_matrix, order_tournament, deduct_bracket, slutspil_filter, pokal_filter


def export_json(db_path: Path, output_dir: Path) -> None:
    with Repository.open_readonly(db_path) as repo:
        backend_pools = repo.get_pools_with_leagues()
        rankings = repo.get_rankings()
        matches = repo.get_matches()

    filtered_pools = backend_pools.loc[backend_pools['season'].ge(2025)].copy() # backend_pools = pool_filter(backend_pools)
    groups, pools, leagues = frontend_pool_grouping(filtered_pools)

    metadata = {
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scraper_version": __version__,
    }
    payloads = []
    pool_validation = {}
    for group_id in groups["group_id"].unique():
        group = groups.loc[groups['group_id'].eq(group_id)]

        tournament_format = group['format'].unique()[0]
        pool_matches = matches.loc[matches["pool_id"].isin(group['pool_id'])]
        pool_rankings = rankings.loc[rankings["pool_id"].isin(group['pool_id'])]

        if tournament_format == 'Robin':
            events, matrix = derive_pool(pool_matches)
            bracket = pd.DataFrame()
            validation = compare_standings(pool_rankings, events)

        elif tournament_format == 'Bracket':
            bracket = derive_bracket(
                leagues=group,
                matches=pool_matches
            )
            events = pd.DataFrame()
            matrix = pd.DataFrame()
            validation = True

        if not validation:
            pool_validation[str(group_id)] = validation

        # Rename fields and convert to records only at the frontend boundary.
        payloads.append((str(group_id), {
            "metadata": {**metadata, "validation": validation},
            "pool": records(frontend_pools(pools.loc[pools["pool_id"].eq(group_id)]))[0],
            "source_standings": records(pool_rankings.assign(pool_id=str(group_id))) if not pool_rankings.empty else [],
            "bracket": records(bracket) if not bracket.empty else [],
            "matches": records(frontend_matches(pool_matches)),
            "cumulative_points": records(events) if not events.empty else [],
            "result_matrix": matrix.astype(object).where(matrix.notna(), None).to_dict(orient="index") if not matrix.empty else {},
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
    for group_id, payload in payloads:
        write_json(output_dir / f"{safe_filename(group_id)}.json", payload)
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
        division=leagues["league_name"].str.replace(r"(?i)\s+(Herrer|Mænd|Kvinder|Damer|Nord|Syd)", "", regex=True).str.strip(),
    )


def frontend_pools(pools: pd.DataFrame) -> pd.DataFrame:
    return pools.rename(columns={"pool_id": "id", "pool_name": "name", "season": "season_id"}).assign(
        pulje_id=pools["pool_id"], id=pools["pool_id"].astype(str), league_id=pools["league_id"].astype(str),
        raekke_id=pools["league_id"], season_id=pools["season"].astype(str),
        season_value=pools["season"].astype(str), season_start_year=pools["season"],
        division=pools["league_name"].str.replace(r"(?i)\s+(Herrer|Mænd|Kvinder|Damer|Nord|Syd)", "", regex=True).str.strip(),
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
        pools['district'].str.lower().eq('volleyball nordjylland') |
        pools['district'].str.lower().eq('midtjysk volleyball') |
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

def frontend_pool_grouping(pools: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = pools.copy()
    df['frontend_league_name'] = df['league_name']
    df['frontend_pool_name'] = df['pool_name']

    liga_idx = df['league_name'].str.contains('volleyligaen', case=False)
    pokal_idx = df['league_name'].str.contains('pokal|lp', case=False)
    bracket_idx = df['league_name'].str.contains('finale|bronze|/|runde', case=False)

    df['format'] = bracket_idx.map({True: 'Bracket', False: 'Robin'})
    df.loc[liga_idx, 'frontend_league_name'] = 'Volleyligaen'
    df.loc[liga_idx & bracket_idx, 'frontend_pool_name'] = 'Slutspil'
    df.loc[liga_idx & ~bracket_idx, 'frontend_pool_name'] = 'Indledende'
    df.loc[pokal_idx, 'frontend_league_name'] = 'Pokalturneringen'
    df.loc[pokal_idx, 'frontend_pool_name'] = 'Række 1'

    df['frontend_pool_id'] = df.groupby(by=['district', 'gender', 'season', 'age_group', 'frontend_league_name', 'frontend_pool_name'])['pool_id'].transform('min')
    df['frontend_league_id'] = df.groupby(by=['district', 'gender', 'season', 'age_group', 'frontend_league_name'])['league_id'].transform('min')

    grouping = df.rename(columns={'frontend_pool_id': 'group_id'})[['format', 'pool_id', 'pool_name', 'league_id', 'league_name', 'district', 'gender', 'season', 'age_group', 'group_id']].copy()
    pools_frontend = df.drop_duplicates('frontend_pool_id', ignore_index=True)[['format', 'frontend_pool_name', 'frontend_league_id', 'frontend_league_name', 'district', 'gender', 'season', 'age_group', 'frontend_pool_id']]
    pools_frontend.columns = pools_frontend.columns.str.removeprefix('frontend_')

    leagues_frontend = df.drop_duplicates('frontend_league_id', ignore_index=True)[['frontend_league_id', 'frontend_league_name', 'district', 'gender', 'season', 'age_group']]
    leagues_frontend.columns = leagues_frontend.columns.str.removeprefix('frontend_')

    return grouping, pools_frontend, leagues_frontend

def derive_pool(matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = calculate_running_points(matches)
    events.rename(columns={"match_time": "date"}, inplace=True)

    matrix = result_matrix(matches).unstack()

    return events, matrix

def derive_bracket(leagues: pd.DataFrame, matches: pd.DataFrame):
    leagues_unique = leagues.drop_duplicates('league_id')
    leagues_unique['round'] = order_tournament(leagues_unique['league_name'])

    df = matches.join(
        other=leagues.set_index('pool_id')[['league_id']],
        on='pool_id'
    ).join(
        other=leagues_unique.set_index('league_id')[['league_name', 'round']],
        on='league_id'
    )[['round', 'league_name', 'match_number', 'home_team', 'away_team', 'home_sets', 'away_sets', 'note']]

    bracket = deduct_bracket(df).drop(columns=['league_name'])

    return bracket


def compare_standings(rankings: pd.DataFrame, events: pd.DataFrame) -> bool:
    current = events.loc[events.groupby(['team'])['game_number'].idxmax()]
    compare = rankings.join(current.set_index('team')[['cumulative_points']], on='team_name')
    validation = bool(compare['points'].eq(compare['cumulative_points']).all())

    return validation


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)

