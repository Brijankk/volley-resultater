import pandas as pd
from pathlib import Path
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.scraper import VolleyballScraper, DISTRICT, AGE_GROUP, GENDERS
from volleyball_resultater.scraper_new import VolleyballScraper as VolleyballScraper2
from volleyball_resultater.paths import DEFAULT_CACHE_DIR

def first_test():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
    scraper = VolleyballScraper(client)
    scraper2 = VolleyballScraper2(client)

    # season_list = scraper2.get_seasons()
    # league_df = scraper2.get_league_ids(DISTRICT, GENDERS[0], 2026, 'U-22')
    pool_df = scraper2.get_pool_ids(2248)
    # pool_df = scraper2.get_pool_ids(2370)
    # scraper2.scrape_pool_schedule(4124)
    m1 = scraper2.scrape_match_results(72486)
    m2 = scraper2.scrape_match_results(72482)
    m3 = scraper2.scrape_match_results(75954)

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

def deduct_tournament(schedule):
    df = schedule.copy()

    df[['Hjemmehold', 'Udehold']] = df[['Hjemmehold', 'Udehold']].apply(sorted, axis=1).to_list()
    df = df.groupby(['runde', 'label_league', 'Hjemmehold', 'Udehold'], as_index=False)['Kampnr.'].max()

    runder = list(df['runde'].drop_duplicates())

    bracket = []
    for runde in sorted(runder, reverse=True)[:-1]:
        df1 = df.loc[df['runde'].eq(runde)]
        df0 = df.loc[df['runde'].eq(runde - 1)]
        df0 = df0.melt(id_vars='Kampnr.', value_vars=['Hjemmehold', 'Udehold'], value_name='hold').set_index('hold')['Kampnr.'].astype(str)

        #Leg1 (hjemmehold)
        df1['leg1'] = df1['Hjemmehold'].str.rsplit('#').apply(lambda x: x[-1])
        df1['leg1'] = df1['leg1'].replace(df0)
        df1.loc[df1['leg1'].str.isdigit().eq(False), 'leg1'] = 'NaN'

        #Leg2 (udehold)
        df1['leg2'] = df1['Udehold'].str.rsplit('#').apply(lambda x: x[-1])
        df1['leg2'] = df1['leg2'].replace(df0)
        df1.loc[df1['leg2'].str.isdigit().eq(False), 'leg2'] = 'NaN'

        bracket.append(df1)
    bracket.append(
        df.loc[df['runde'].eq(0)].assign(
            leg1='NaN',
            leg2='NaN',
        )
    )
    bracket = pd.concat(bracket)
    bracket.loc[bracket['label_league'].str.contains('bronze', case=False), ['leg1', 'leg2']] = 'NaN'

    return bracket

def order_tournament(tournament_labels: pd.Series[str]) -> pd.Series[int]:
    df = tournament_labels.to_frame('label')

    df['is_final'] = df['label'].str.contains('finale', case=False)
    df['final_prefix'] = df['label'].str.lower().str.extract(
        pat=r"(?:^|\s)([^\s-]+)-?finaler?\b"
    ).fillna('1/1').replace({'semi': '1/2', 'kvart': '1/4'})
    df['runde_prefix'] = df['label'].str.lower().str.extract(r"\b(\d+)\.\s*runde\b")
    
    df = df.sort_values(by=['is_final', 'final_prefix', 'runde_prefix'], ascending=[False, True, False])
    df['round'] = range(df.shape[0])
    df.loc[df['label'].str.contains('bronze', case=False), 'round'] = 0

    df['round'] = df['round'].max() - df['round']

    return df['round']

def test_tournament_order():
    leagues = get_all_leagues()
    pokal_leagues = leagues.loc[
        (
            leagues['label'].str.contains('Pokal', case=False) |
            leagues['label'].str.contains('LP')
        ) &
        ~leagues['label'].str.contains('Seed') &
        ~leagues['label'].str.contains('Kreds')
    ]

    pokal_leagues['round'] = pokal_leagues.groupby(['gender', 'season'])['label'].apply(order_tournament).droplevel(['gender', 'season'])

    pokal_leagues.sort_values(['season', 'gender', 'round']).to_clipboard()

    return pokal_leagues

def test_slutspil_order():
    leagues = get_all_leagues()
    slutspil = leagues.loc[
        leagues['label'].str.contains('Volleyligaen', case=False) &
        ~leagues['label'].str.contains('pokal', case=False) &
        (
            leagues['label'].str.contains('finale', case=False) |
            leagues['label'].str.contains('bronze', case=False)
        )
    ]

    slutspil['round']= slutspil.groupby(['gender', 'season'])['label'].apply(order_tournament).droplevel(['gender', 'season'])

    slutspil.sort_values(['season', 'gender', 'round']).to_clipboard()

    return slutspil

def pokalturnering(season, gender):
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0)
    scraper = VolleyballScraper2(client)
    leagues = scraper.get_league_ids(DISTRICT, gender, season, AGE_GROUP)

    pokal_leagues = leagues.loc[
        (
            leagues['label'].str.contains('Pokal', case=False) |
            leagues['label'].str.contains('LP')
        ) &
        ~leagues['label'].str.contains('Seed') &
        ~leagues['label'].str.contains('Kreds')
    ]
    pokal_leagues['runde'] = order_tournament(pokal_leagues['label'])

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
    )[['runde', 'label_league', 'Kampnr.', 'Hjemmehold', 'Udehold', 'Resultat']]

    tournament = deduct_tournament(df)
    
    return df

def liga_slutspil(season, gender):
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0)
    scraper = VolleyballScraper2(client)
    leagues = scraper.get_league_ids(DISTRICT, gender, season, AGE_GROUP)

    slutspil = leagues.loc[
        leagues['label'].str.contains('Volleyligaen', case=False) &
        ~leagues['label'].str.contains('pokal', case=False) &
        (
            leagues['label'].str.contains('finale', case=False) |
            leagues['label'].str.contains('bronze', case=False)
        )
    ]
    slutspil['runde'] = order_tournament(slutspil['label'])

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
    )[['runde', 'label_league', 'Kampnr.', 'Hjemmehold', 'Udehold', 'Resultat']]

    tournament = deduct_tournament(df)

    return

if __name__ == '__main__':
    # test_slutspil_order()
    get_all_leagues()
    # first_test()
    pokalturnering(2026, "Mand")
    liga_slutspil(2025, "Mand")