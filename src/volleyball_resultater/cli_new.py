from __future__ import annotations

import argparse
from pathlib import Path
import sys
import sqlite3

import pandas as pd

from .client import ResultaterClient
from .exporter import export_json
from .paths import PROJECT_ROOT, DEFAULT_CACHE_DIR, DEFAULT_DB_PATH, DEFAULT_EXPORT_DIR
from .rules import computed_standings, rules_for_league
from .scraper_new import DISTRICT, AGE_GROUP, GENDERS, VolleyballScraper
from .storage_new import Repository
from .validation import validate_rankings

def main(season: str|int="Nuværende"):
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
    scraper = VolleyballScraper(client)
    repo = Repository(DB_PATH = PROJECT_ROOT / "data" / "volleyball2.sqlite")

    seasons = scraper.get_seasons()
    test_league = scraper.get_league_ids(DISTRICT, GENDERS[0], "Nuværende", AGE_GROUP)
    liga_id = test_league.set_index('name')['id']['Volleyligaen Herrer']
    liga_pool = scraper.get_pool_ids(liga_id)
    liga_schedule = scraper.scrape_pool_schedule(liga_pool.loc[0, 'id'])
    seasons.loc[seasons['text'].eq('Nuværende'), 'year'] = liga_schedule['match_time'].min().year

    leagues = {}
    for gender in GENDERS:
        league = scraper.get_league_ids(DISTRICT, gender, season, AGE_GROUP)
        leagues[(gender, season)] = league
    leagues = pd.concat(leagues, names=['gender', 'season']).droplevel(-1).reset_index()
    leagues['district'] = DISTRICT
    leagues['age_group'] = AGE_GROUP

    filter = leagues.loc[
        (
            leagues['name'].str.contains('. div', case=False) &
            ~leagues['name'].str.contains('kval', case=False)
        ) |
        (
            (
                leagues['name'].str.contains('Pokal', case=False) |
                leagues['name'].str.contains('LP')
            ) &
            ~leagues['name'].str.contains('Seed') &
            ~leagues['name'].str.contains('Kreds')
        )
    ]
    league_filtred = leagues.loc[
        (
            leagues['name'].str.contains('. div', case=False) &
            ~leagues['name'].str.contains('kval', case=False)
        ) |
        (
            leagues['name'].str.lower().eq('volleyligaen herrer') |
            leagues['name'].str.lower().eq('volleyligaen kvinder')
        )
    ]

    pools = {}
    for league_id in league_filtred['id']:
        pools[league_id] = scraper.get_pool_ids(league_id)
    pools = pd.concat(pools, names=['league_id']).droplevel(-1).reset_index()

    rankings = {}
    for pool_id in pools['id']:
        rankings[pool_id] = scraper.scrape_pool_scoreboard(pool_id)
    rankings = pd.concat(rankings, names=['pool_id']).droplevel(-1).reset_index()

    schedules = {}
    for pool_id in pools['id']:
        schedules[pool_id] = scraper.scrape_pool_schedule(pool_id)
    schedules = pd.concat(schedules, names=['pool_id']).droplevel(-1).reset_index()

    match_details = {}
    for match_id in schedules['id']:
        match_details[match_id] = scraper.scrape_match_details(match_id)
    match_details = pd.concat(match_details, names=['id']).droplevel(-1).reset_index()

    matches = schedules.merge(match_details, on='id')

    repo.save_league(league_filtred)
    repo.save_pool(pools)
    repo.upsert_ranking(rankings)
    repo.upsert_matches(matches)
    repo.commit()

    return

if __name__ == "__main__":
    pass
