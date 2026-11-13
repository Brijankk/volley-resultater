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
        pools = repo.get_pools_with_leagues()
        rankings = repo.get_rankings()
        matches = repo.get_matches()

    pools = pools.loc[pools['season'].ge(2026)].copy() # pools = pool_filter(pools)
    leagues = pools[
        ['league_id', 'league_name', 'district', 'gender', 'age_group', 'season']
    ].drop_duplicates(
        ignore_index=True
    ).sort_values(
        by=['season', 'gender', 'league_name', 'league_id'],
        ascending=[False, True, True, True]
    )
    pool_groups = group_pools(pools)

    metadata = {
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scraper_version": __version__,
    }
    payloads = []
    pool_validation = {}
    for group_id in pool_groups["group_id"].unique():
        group = pool_groups.loc[pool_groups['group_id'].eq(group_id)]

        tournament_format = group['format'].unique()[0]
        pool_matches = matches.loc[matches["pool_id"].isin(group['pool_id'])]
        pool_rankings = rankings.loc[rankings["pool_id"].isin(group['pool_id'])]

        if tournament_format == 'Robin':

            events, matrix = derive_pool(pool_matches)
        
            validation = compare_standings(pool_rankings, events)

            bracket = pd.DataFrame()

        elif tournament_format == 'Bracket':

            bracket = derive_bracket(
                leagues=group,
                matches=pool_matches
            )
            validation = True

            events = pd.DataFrame()
            matrix = pd.DataFrame()

        if not validation:
            pool_validation[str(group_id)] = validation

        # Rename fields and convert to records only at the frontend boundary.
        payloads.append((str(group_id), {
            "metadata": {**metadata, "validation": validation, "format": tournament_format},
            "pool": records(frontend_pools(pools.loc[pools["pool_id"].eq(group_id)]))[0],
            "source_standings": records(pool_rankings.assign(pool_id=str(group_id))) if not pool_rankings.empty else [],
            "bracket": records(bracket) if not bracket.empty else [],
            "matches": records(frontend_matches(pool_matches)),
            "cumulative_points": records(events) if not events.empty else [],
            "result_matrix": matrix.astype(object).where(matrix.notna(), None).to_dict(orient="index") if not matrix.empty else {},
        }))

    pools_meta = pool_groups.sort_values('league_id').drop_duplicates('group_id').drop(columns=['pool_id']).rename(columns={'group_id': 'pool_id'})
    pools_meta['pool_name'] = pools_meta['pool_name'].where(pools_meta['format'].eq('Robin'), 'Række 1')
    leagues_meta = pools_meta.drop_duplicates('league_id')
    leagues_meta['league_name'] = leagues_meta['league_name'].where(leagues_meta['format'].eq('Robin'), leagues_meta['group_name'])
    # leagues_meta.loc[leagues_meta['group_name'].eq('slutspil'), 'league_name'] = "Volleyliga slutspil"
    # leagues_meta.loc[leagues_meta['group_name'].eq('pokal'), 'league_name'] = "Pokalturnering"
    index = {
        "metadata": {
            **metadata,
            "seasons": sorted(leagues_meta["season"].astype(str).unique(), reverse=True),
            "league_count": len(leagues_meta),
            "pool_count": len(pools_meta)
        },
        # "leagues": records(frontend_leagues(leagues)),
        "leagues": records(frontend_leagues(leagues_meta).drop(columns=['pool_id', 'pool_name', 'group_name'])),
        # "pools": records(frontend_pools(pools)[['id', 'name', 'league_id']]),
        "pools": records(frontend_pools(pools_meta)[['id', 'name', 'league_id']]),
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

def group_pools(pools: pd.DataFrame) -> pd.DataFrame:
    robins = pools.copy()
    robins['group_name'] = robins['pool_name']
    robins['group_id'] = robins['pool_id']

    brackets = pd.concat(
        objs=[
            pokal_filter(pools),
            slutspil_filter(pools),
        ],
        keys=['Pokalturnering', 'Volleyliga slutspil'],
        names=['group_name'],
    ).droplevel(-1).reset_index()
    brackets['group_id'] = brackets.groupby(by=['district', 'gender', 'season', 'age_group', 'group_name'])['pool_id'].transform(min)

    pool_groups = pd.concat(
        objs=[
            robins,
            brackets,
        ],
        keys=['Robin', 'Bracket'],
        names=['format']
    ).droplevel(-1).reset_index().drop_duplicates(
        subset='pool_id',
        keep='last',
        ignore_index=True,
    )
    
    # pokal = pokal_filter(pools).assign(pool_name='pokal', league_name='pokal', style='Bracket')
    # slutspil = slutspil_filter(pools).assign(pool_name='slutspil', league_name='slutspil', style='Bracket')

    # df = pd.concat(
    #     objs=[
    #         pools,
    #         pokal,
    #         slutspil
    #     ],
    # ).drop_duplicates(
    #     subset='pool_id',
    #     keep='last',
    #     ignore_index=True,
    # )
    # df['style'] = df['style'].fillna('Robin')

    # pool_groups = df.groupby(
    #     by=['district', 'gender', 'season', 'age_group', 'pool_name', 'league_name', 'style'],
    #     as_index=False
    # ).aggregate({'pool_id': ['min', list], 'league_id': ['min', list]})
    # pool_groups.rename(columns={'min': '', 'list': 's'}, inplace=True)
    # pool_groups.columns = pool_groups.columns.map(''.join)

    return pool_groups

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

