import pandas as pd
from pathlib import Path
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.scraper_old import VolleyballScraper as VolleyballScraper_old, DISTRICT, AGE_GROUP, GENDERS
from volleyball_resultater.scraper import VolleyballScraper as VolleyballScraper
from volleyball_resultater.paths import PROJECT_ROOT, DEFAULT_CACHE_DIR, DEFAULT_DB_PATH_OLD, DEFAULT_DB_PATH, DEFAULT_EXPORT_DIR_OLD, DEFAULT_EXPORT_DIR
from volleyball_resultater.storage import Repository
from volleyball_resultater.wrangling import order_tournament, deduct_tournament

def test_scraper_old():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
    scraper = VolleyballScraper_old(client)
    
    seasons = scraper.seasons()
    season = next(s for s in seasons if s.id == "2025")

    leagues = scraper.leagues_for(season, "Mand")
    league = leagues[-1]

    pool_data = scraper.scrape_league(league)

def test_scraper():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
    scraper = VolleyballScraper(client, append_parameters=True)

    age_groups = scraper.get_age_groups()
    league_df = scraper.get_league_ids(DISTRICT, GENDERS[0], season=2026, age_group='Senior')
    # pool_df = scraper.get_pool_ids(2248)
    # pool_df = scraper.get_pool_ids(2372)
    scraper.scrape_pool_schedule(4124) # No matches played
    scraper.scrape_pool_schedule(4151) # Incomplete matches
    scraper.scrape_pool_schedule(4123) # Some matches miss starttime



def get_all_leagues():
    from itertools import product

    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0.25, refresh_cache=False)
    scraper = VolleyballScraper(client, append_parameters=True)

    seasons = scraper._get_season_overview()

    
    DISTRICTS = ['Volleyball Danmark', 'Sjællands Volleyball Kreds', 'Fyns Volleyball Kreds', 'Volleyball Sydjylland', 'Midtjysk Volleyball', 'Volleyball Nordjylland', 'Grønlands Volleyballforbund']
    AGE_GROUPS = ['Oldies', 'Senior', 'U-22', 'U-21', 'U-20', 'U-19', 'U-18', 'U-17', 'U-16', 'U-15', 'U-14']

    leagues = []
    for district, gender, season, age_group in product(DISTRICTS, GENDERS, seasons['year'], AGE_GROUPS):
        league = scraper.get_league_ids(district, gender, season, age_group)
        leagues.append(league)

    leagues_df = pd.concat(leagues).reset_index(drop=True)

    return leagues_df



def test_tournament_order():
    leagues = get_all_leagues()
    pokal_leagues = leagues.loc[
        (
            leagues['name'].str.contains('Pokal', case=False) |
            leagues['name'].str.contains('LP')
        ) &
        ~leagues['name'].str.contains('Seed') &
        ~leagues['name'].str.contains('Kreds')
    ]

    pokal_leagues['round'] = pokal_leagues.groupby(['gender', 'season'])['name'].apply(order_tournament).droplevel(['gender', 'season'])

    pokal_leagues.sort_values(['season', 'gender', 'round']).to_clipboard()

    return pokal_leagues

def test_slutspil_order():
    leagues = get_all_leagues()
    slutspil = leagues.loc[
        leagues['name'].str.contains('Volleyligaen', case=False) &
        ~leagues['name'].str.contains('pokal', case=False) &
        (
            leagues['name'].str.contains('finale', case=False) |
            leagues['name'].str.contains('bronze', case=False)
        )
    ]

    slutspil['round']= slutspil.groupby(['gender', 'season'])['name'].apply(order_tournament).droplevel(['gender', 'season'])

    slutspil.sort_values(['season', 'gender', 'round']).to_clipboard()

    return slutspil

def pokalturnering(season, gender):
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0)
    scraper = VolleyballScraper(client)
    leagues = scraper.get_league_ids(DISTRICT, gender, season, AGE_GROUP)

    pokal_leagues = leagues.loc[
        (
            leagues['name'].str.contains('Pokal', case=False) |
            leagues['name'].str.contains('LP')
        ) &
        ~leagues['name'].str.contains('Seed') &
        ~leagues['name'].str.contains('Kreds')
    ]
    pokal_leagues['runde'] = order_tournament(pokal_leagues['name'])

    pokal_pools = {}
    for league_id in pokal_leagues['id']:
        pokal_pools[league_id] = scraper.get_pool_ids(league_id)
    pools = pd.concat(pokal_pools, names=['league_id']).droplevel(-1)

    schedule = {}
    for pool_id in pools['id']:
        schedule[pool_id] = scraper.scrape_pool_schedule(pool_id)
    schedule = pd.concat(schedule, names=['pool_id']).droplevel(-1)

    df = pokal_leagues.join(
        other=pools,
        on='id',
        rsuffix='_pool',
        lsuffix='_league'
    ).join(
        other=schedule,
        on='id_pool',
    )[['runde', 'name_league', 'Kampnr.', 'Hjemmehold', 'Udehold', 'Resultat']]

    tournament = deduct_tournament(df)
    
    return df

def liga_slutspil(season, gender):
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0)
    scraper = VolleyballScraper(client)
    leagues = scraper.get_league_ids(DISTRICT, gender, season, AGE_GROUP)

    slutspil = leagues.loc[
        leagues['name'].str.contains('Volleyligaen', case=False) &
        ~leagues['name'].str.contains('pokal', case=False) &
        (
            leagues['name'].str.contains('finale', case=False) |
            leagues['name'].str.contains('bronze', case=False)
        )
    ]
    slutspil['runde'] = order_tournament(slutspil['name'])

    slut_pools = {}
    for league_id in slutspil['id']:
        slut_pools[league_id] = scraper.get_pool_ids(league_id)
    pools = pd.concat(slut_pools, names=['league_id']).droplevel(-1)

    schedule = {}
    for pool_id in pools['id']:
        schedule[pool_id] = scraper.scrape_pool_schedule(pool_id)
    schedule = pd.concat(schedule, names=['pool_id']).droplevel(-1)

    df = slutspil.join(
        other=pools,
        on='id',
        rsuffix='_pool',
        lsuffix='_league'
    ).join(
        other=schedule,
        on='id_pool',
    )[['runde', 'name_league', 'Kampnr.', 'Hjemmehold', 'Udehold', 'Resultat']]

    tournament = deduct_tournament(df)

    return

def test_repo():
    DB_PATH = PROJECT_ROOT / "data" / "volleyball_new.sqlite"
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0.25, refresh_cache=False)
    scraper = VolleyballScraper(client)
    repo = Repository(DB_PATH)

    season = 2025
    leagues = {}
    for gender in GENDERS:
        league = scraper.get_league_ids(DISTRICT, gender, season, AGE_GROUP)
        leagues[(gender, season)] = league
    leagues_df = pd.concat(leagues, names=['gender', 'season']).droplevel(-1).reset_index()
    leagues_df['district'] = DISTRICT
    leagues_df['age_group'] = AGE_GROUP
    leagues_df['name'] = leagues_df['name']

    league_filtered = leagues_df.loc[
        (
            leagues_df['name'].str.contains('. div', case=False) &
            ~leagues_df['name'].str.contains('kval', case=False)
        )
    ]
    pools = {}
    for league_id in league_filtered['id']:
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
    for match_id in schedules['id'].head(10):
        match_details[match_id] = scraper.scrape_match_details(match_id)
    match_details = pd.concat(match_details, names=['id']).droplevel(-1).reset_index()

    matches = schedules.merge(match_details, on='id')

    repo.upsert_leagues(leagues_df)
    repo.upsert_pools(pools)
    repo.upsert_rankings(rankings)
    repo.upsert_matches(matches)
    repo.commit()
    repo.close()

    return

def run_main():
    from volleyball_resultater.cli import main
    main([
        "--season", "current",
        "--db", str(DEFAULT_DB_PATH),
        "--refresh-cache",
        "--export-dir", str(DEFAULT_EXPORT_DIR),
        "--no-export",
    ])


def run_old_main():
    from volleyball_resultater.cli_old import main
    main([
        # "--season", "current",
        "--db", str(DEFAULT_DB_PATH_OLD),
        "--export-dir", str(DEFAULT_EXPORT_DIR_OLD),
        # "--no-export",
    ])

def test_old_exporter():
    from volleyball_resultater.exporter_old import export_json
    export_json(DEFAULT_DB_PATH_OLD, DEFAULT_EXPORT_DIR_OLD)

def test_new_exporter():
    from volleyball_resultater.exporter import export_json
    export_json(DEFAULT_DB_PATH, Path(str(DEFAULT_EXPORT_DIR) + '_test'))

if __name__ == '__main__':
    # test_slutspil_order()
    # get_all_leagues()
    # test_scraper()
    # pokalturnering(2026, "Kvinde")
    # liga_slutspil(2025, "Mand")
    # test_repo()
    run_main()
    # test_new_exporter()