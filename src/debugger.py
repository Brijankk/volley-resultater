import pandas as pd
from pathlib import Path
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.scraper import VolleyballScraper as VolleyballScraper, DISTRICT, AGE_GROUP, GENDERS
from volleyball_resultater.paths import PROJECT_ROOT, DEFAULT_CACHE_DIR, DEFAULT_DB_PATH, DEFAULT_EXPORT_DIR
from volleyball_resultater.storage import Repository
from volleyball_resultater.wrangling import order_tournament, deduct_tournament

def test_scraper():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
    scraper = VolleyballScraper(client, append_parameters=True)

    age_groups = scraper.get_age_groups()
    league_df = scraper.get_league_ids(DISTRICT, GENDERS[0], season=2026, age_group='Senior')
    pool_df = scraper.get_pool_ids(2248)
    pool_df = scraper.get_pool_ids(2372)
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

def scrape_tournaments():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0.25, refresh_cache=False)
    scraper = VolleyballScraper(client)
    repo = Repository(DEFAULT_DB_PATH)

    def pokal_filter(df: pd.DataFrame) -> pd.DataFrame:
        df = df.loc[
            (
                df['name'].str.contains('Pokal', case=False) |
                df['name'].str.contains('LP')
            ) &
            ~df['name'].str.contains('Seed') &
            ~df['name'].str.contains('Kreds'),
        ].copy()

        return df

    def slutspil_filter(df: pd.DataFrame) -> pd.DataFrame:
        df = df.loc[
            df['name'].str.contains('Volleyligaen', case=False) &
            (
                df['name'].str.contains('finale', case=False) |
                df['name'].str.contains('bronze', case=False)
            ),
        ].copy()

        return df

    all_leagues = repo.get_leagues()
    all_leagues = all_leagues.loc[all_leagues['season'].eq(2025) & all_leagues['age_group'].eq('Senior') & all_leagues['district'].eq('Volleyball Danmark')]
    pokal = pokal_filter(all_leagues)
    slutspil = slutspil_filter(all_leagues)
    bracket_leagues = pd.concat([pokal, slutspil])

    bracket_pools = {}
    for league_id in bracket_leagues['id']:
        bracket_pools[league_id] = scraper.get_pool_ids(league_id)
    pools = pd.concat(bracket_pools, names=['league_id']).droplevel(-1)

    schedule = {}
    for pool_id in pools['id']:
        schedule[pool_id] = scraper.scrape_pool_schedule(pool_id)
    schedules = pd.concat(schedule, names=['pool_id']).droplevel(-1)

    match_details_list = {}
    for match_id in schedules['match_id']:
        match_details_list[match_id] = scraper.scrape_match_details(match_id)
    match_details = pd.concat(match_details_list, names=['match_id']).droplevel(-1)

    matches = schedules.reset_index().merge(match_details, on='match_id').rename(columns={'match_id': 'id'})
    
    repo.upsert_pools(pools.reset_index())
    repo.upsert_matches(matches)
    repo.commit()
    repo.close()

    pass

def test_repo():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0.25, refresh_cache=False)
    scraper = VolleyballScraper(client)
    repo = Repository(DEFAULT_DB_PATH)

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
        # "--season", "2021",
        # "--season", "2022",
        # "--season", "2023",
        # "--season", "2024",
        # "--season", "2025",
        # "--season", "2026",
        "--season", "current",
        "--refresh-cache",
        # "--db", str(DEFAULT_DB_PATH),
        # "--export-dir", str(DEFAULT_EXPORT_DIR),
        # "--no-export",
    ])

def test_exporter():
    from volleyball_resultater.exporter import export_json
    export_json(DEFAULT_DB_PATH, Path(str(DEFAULT_EXPORT_DIR) + '_test'))

if __name__ == '__main__':
    # get_all_leagues()
    test_scraper()
    # scrape_tournaments()
    # test_repo()
    # run_main()
    # test_exporter()