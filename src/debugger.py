import pandas as pd
from pathlib import Path
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.scraper import VolleyballScraper, DISTRICT, AGE_GROUP, GENDERS
from volleyball_resultater.scraper_new import VolleyballScraper as VolleyballScraper2
from volleyball_resultater.paths import PROJECT_ROOT, DEFAULT_CACHE_DIR, DEFAULT_DB_PATH
from volleyball_resultater.storage_new import Repository
from volleyball_resultater.wrangling import order_tournament, deduct_tournament

def first_test():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
    scraper = VolleyballScraper(client)
    scraper2 = VolleyballScraper2(client)

    # season_list = scraper2.get_seasons()
    # league_df = scraper2.get_league_ids(DISTRICT, GENDERS[0], 2026, 'U-22')
    # pool_df = scraper2.get_pool_ids(2248)
    # pool_df = scraper2.get_pool_ids(2370)
    scraper2.scrape_pool_schedule(4124) # No matches played
    scraper2.scrape_pool_schedule(4151) # Incomplete matches
    scraper2.scrape_pool_schedule(4123) # Some matches miss starttime


    seasons = scraper.seasons()
    season = next(s for s in seasons if s.id == "2025")

    leagues = scraper.leagues_for(season, "Mand")
    league = leagues[-1]

    pool_data = scraper.scrape_league(league)

def get_all_leagues():
    from itertools import product

    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0.25, refresh_cache=False)
    scraper = VolleyballScraper2(client)

    seasons = scraper.get_seasons()

    leagues = {}
    for gender, season in product(GENDERS, seasons['year']):
        league = scraper.get_league_ids(DISTRICT, gender, season, AGE_GROUP)
        leagues[(gender, season)] = league

    leagues_df = pd.concat(leagues, names=['gender', 'season']).droplevel(-1).reset_index()

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
    scraper = VolleyballScraper2(client)
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
    scraper = VolleyballScraper2(client)
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
    DB_PATH = PROJECT_ROOT / "data" / "volleyball2.sqlite"
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0.25, refresh_cache=False)
    scraper = VolleyballScraper2(client)
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

    repo.save_league(leagues_df)
    repo.commit()
    repo.close()

    return

def run_main():
    from volleyball_resultater.cli_new import main
    main(2025)

if __name__ == '__main__':
    # test_slutspil_order()
    # get_all_leagues()
    # first_test()
    # pokalturnering(2026, "Kvinde")
    # liga_slutspil(2025, "Mand")
    # test_repo()
    run_main()