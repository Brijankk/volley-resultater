from __future__ import annotations

import argparse
from pathlib import Path
import sys
import sqlite3

from .client import ResultaterClient
from .exporter import export_json
from .paths import DEFAULT_CACHE_DIR, DEFAULT_DB_PATH, DEFAULT_EXPORT_DIR
from .rules import computed_standings, rules_for_league
from .scraper import GENDERS, VolleyballScraper
from .storage import Repository
from .validation import validate_rankings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Danish volleyball league results.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite database path.")
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR, help="JSON export directory.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Raw HTML cache directory.")
    parser.add_argument("--season", action="append", help="Season value to scrape, for example 2025. May be repeated.")
    parser.add_argument("--all-seasons", action="store_true", help="Scrape every discovered season.")
    parser.add_argument("--no-export", action="store_true", help="Skip JSON export after scraping.")
    parser.add_argument("--validate", action="store_true", help="Compare computed standings with official standings after scraping.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate the existing SQLite database.")
    parser.add_argument("--throttle", type=float, default=0.25, help="Seconds to pause after live requests.")
    args = parser.parse_args(argv)

    if args.validate_only:
        return run_validation(args.db)

    client = ResultaterClient(cache_dir=args.cache_dir, throttle_seconds=args.throttle)
    scraper = VolleyballScraper(client)
    seasons = scraper.seasons()
    if args.season:
        wanted = set(args.season)
        seasons = [season for season in seasons if season.value in wanted or season.id in wanted]
    elif not args.all_seasons:
        seasons = [season for season in seasons if season.is_current]

    if not seasons:
        print("No matching seasons found.", file=sys.stderr)
        return 2

    repo = Repository(args.db)
    try:
        for season in seasons:
            print(f"Season: {season.label}")
            repo.save_season(season)
            for gender in GENDERS:
                leagues = scraper.leagues_for(season, gender)
                for league in leagues:
                    print(f"  {league.name}")
                    repo.save_league(league)
                    for pool_data in scraper.scrape_league(league):
                        print(f"    {pool_data.pool.name}: {len(pool_data.matches)} matches")
                        repo.save_pool(pool_data.pool)
                        repo.replace_source_standings(pool_data.pool.id, pool_data.standings)
                        repo.replace_matches(pool_data.pool.id, pool_data.matches, pool_data.set_results)
                        rule_profile = rules_for_league(season, league, pool_data.pool)
                        computed = computed_standings(pool_data.pool.id, pool_data.matches, pool_data.set_results, rule_profile)
                        repo.replace_computed_standings(pool_data.pool.id, rule_profile.id, computed)
                    repo.commit()
        repo.commit()
    finally:
        repo.close()

    if not args.no_export:
        export_json(args.db, args.export_dir)
        print(f"Exported JSON to {args.export_dir}")
    if args.validate:
        validation_code = run_validation(args.db)
        if validation_code:
            return validation_code
    print(f"Saved SQLite data to {args.db}")
    return 0


def run_validation(db_path: Path) -> int:
    connection = sqlite3.connect(db_path)
    try:
        mismatches = validate_rankings(connection)
    finally:
        connection.close()
    if not mismatches:
        print("Computed standings match official standings.")
        return 0
    print(f"Found {len(mismatches)} computed-vs-official standing differences:")
    print("These can indicate parser/rule drift, or administrative results that are present in standings but not reconstructable from the ordinary schedule rows.")
    for item in mismatches[:50]:
        print(
            f"- {item.league_name} / {item.pool_name} / {item.team_name}: "
            f"{item.field} official={item.official!r} computed={item.computed!r}"
        )
    if len(mismatches) > 50:
        print(f"...and {len(mismatches) - 50} more.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
