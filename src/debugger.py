import pandas as pd
from pathlib import Path
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.scraper import VolleyballScraper
from volleyball_resultater.scraper_new import VolleyballScraper as VolleyballScraper2
from volleyball_resultater.paths import DEFAULT_CACHE_DIR

def first_test():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0)
    scraper = VolleyballScraper(client)
    scraper2 = VolleyballScraper2(client)

    # scraper2.scrape_pool_schedule(4124)
    m1 = scraper2.scrape_match_results(72486)
    m2 = scraper2.scrape_match_results(72482)
    m3 = scraper2.scrape_match_results(75954)

    seasons = scraper.seasons()
    season = next(s for s in seasons if s.id == "2025")

    leagues = scraper.leagues_for(season, "Mand")
    league = leagues[-1]

    pool_data = scraper.scrape_league(league)

def deduct_tournament(schedule):
    df = schedule.copy()

    runder = list(df['runde'].drop_duplicates())

    for runde in sorted(runder, reverse=True)[:-1]
        df1 = df.loc[df['runde'].eq(runde)]
        df0 = df.loc[df['runde'].eq(runde - 1)]
        df0 = df0.melt(id_vars='Kampnr.', value_vars=['Hjemmehold', 'Udehold'], value_name='hold').set_index('hold')['Kampnr.']

        #Leg1 (hjemmehold)
        df1['leg1'] = df1['Hjemmehold'].str.rsplit('#').apply(lambda x: x[-1])
        df1['leg1'] = df1['leg1'].replace(df0)
        df1.loc[df1['leg1'].str.isdigit().eq(False), 'leg1'] = 'NaN'

        #Leg2 (udehold)
        df1['leg2'] = df1['Udehold'].str.rsplit('#').apply(lambda x: x[-1])
        df1['leg2'] = df1['leg2'].replace(df0)
        df1.loc[df1['leg2'].str.isdigit().eq(False), 'leg2'] = 'NaN'





def pokalturnering26():
    client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0)
    scraper = VolleyballScraper2(client)
    pool_id = {
        (1, 'øst'): 4151,
        (1, 'vest'): 4152,
        (2, 'øst'): 4153,
        (2, 'vest'): 4154,
    }

    pools = []
    for id in  pool_id.values():
        pool_schedule = scraper.scrape_pool_schedule(id)
        pools.append(pool_schedule)
    schedule = pd.concat(pools, keys=pool_id.keys(), names=['runde', 'region']).droplevel(-1).reset_index()

    df = schedule[['runde', 'Kampnr.', 'Hjemmehold', 'Udehold', 'Resultat']]

    return

if __name__ == '__main__':
    pokalturnering26()