from __future__ import annotations

import sys
import argparse
from pathlib import Path
from itertools import product

import pandas as pd

from .client import ResultaterClient
from .exporter import export_json
from .paths import DEFAULT_CACHE_DIR, DEFAULT_DB_PATH, DEFAULT_EXPORT_DIR
from .scraper import DISTRICT, AGE_GROUP, GENDERS, VolleyballScraper
from .storage import Repository

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Danish volleyball league results.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite database path.")
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR, help="JSON export directory.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Raw HTML cache directory.")
    parser.add_argument("--season", action="append", help="Season value to scrape, for example 2025. May be repeated.")
    parser.add_argument("--no-export", action="store_true", help="Skip JSON export after scraping.")
    parser.add_argument("--throttle", type=float, default=0.25, help="Seconds to pause after live requests.")
    parser.add_argument("--refresh-cache", action="store_true", help="Fetch fresh HTML instead of reusing cached pages.")
    args = parser.parse_args(argv)


    client = ResultaterClient(cache_dir=args.cache_dir, throttle_seconds=args.throttle, refresh_cache=args.refresh_cache)
    scraper = VolleyballScraper(client, append_parameters=True)
    repo = Repository(args.db)

    season_overview = scraper._get_season_overview()
    seasons = [int(season) for season in args.season if season.isdigit()]
    if "current" in args.season:
        seasons.append(season_overview.set_index("text")["year"]["Nuværende"])

    if set(seasons).difference(season_overview["year"]):
        print("One or more seasons not found.", file=sys.stderr)
        return 2
    
    league_list = []
    for gender, season in product(GENDERS, seasons):
        league = scraper.get_league_ids(DISTRICT, gender, season, AGE_GROUP)
        league_list.append(league)
    leagues = pd.concat(league_list).reset_index(drop=True)
    leagues_filtered = league_filter(leagues)

    pool_list = []
    for league_id in leagues_filtered['league_id']:
        pool_list.append(scraper.get_pool_ids(league_id))
    pools = pd.concat(pool_list).reset_index(drop=True)

    rank_list = []
    for pool_id in pools['pool_id']:
        rank_list.append(scraper.scrape_pool_scoreboard(pool_id))
    rankings = pd.concat(rank_list).reset_index(drop=True)

    schedule_list = []
    for pool_id in pools['pool_id']:
        schedule_list.append(scraper.scrape_pool_schedule(pool_id))
    schedules = pd.concat(schedule_list).reset_index(drop=True)

    match_details_list = []
    for match_id in schedules['match_id']:
        match_details_list.append(scraper.scrape_match_details(match_id))
    match_details = pd.concat(match_details_list).reset_index(drop=True)

    matches = schedules.merge(match_details, on='match_id')

    try:
        repo.upsert_leagues(leagues_filtered)
        repo.upsert_pools(pools)
        repo.upsert_rankings(rankings)
        repo.upsert_matches(matches)
        repo.commit()
    finally:
        repo.close()

    if not args.no_export:
        export_json(args.db, args.export_dir)
        print(f"Exported JSON to {args.export_dir}")

    return 0

def league_filter(leagues_df: pd.DataFrame) -> pd.DataFrame:
    df = leagues_df
    leagues_filtered = df.loc[
        (
            df['league_name'].str.contains('. div', case=False) &
            ~df['league_name'].str.contains('kval', case=False)
        ) |
        (
            (
                df['league_name'].str.contains('Pokal', case=False) |
                df['league_name'].str.contains('LP')
            ) &
            ~df['league_name'].str.contains('Seed') &
            ~df['league_name'].str.contains('Kreds')
        )
    ].copy()

    leagues_filtered = df.loc[
        (
            df['league_name'].str.contains('. div', case=False) &
            ~df['league_name'].str.contains('kval', case=False)
        ) |
        (
            df['league_name'].str.lower().eq('volleyligaen herrer') |
            df['league_name'].str.lower().eq('volleyligaen kvinder')
        )
    ].copy()

    return leagues_filtered


if __name__ == "__main__":
    raise SystemExit(main())
