from __future__ import annotations

import unittest

import pandas as pd

from volleyball_resultater.scraper import VolleyballScraper
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.paths import PROJECT_ROOT, DEFAULT_CACHE_DIR, DEFAULT_DB_PATH
from volleyball_resultater.wrangling import calculate_running_rankings, result_matrix, order_tournament, deduct_tournament
from volleyball_resultater.storage import Repository

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

class WranglingTests(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        self.client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
        self.scraper = VolleyballScraper(self.client)
        self.repo = Repository(DEFAULT_DB_PATH)

        super().__init__(methodName)

    def test_running_ranking(self):

        pass

    def test_result_matrix(self):
        sch1 = self.scraper.scrape_pool_schedule(4124) # No matches played
        sch2 = self.scraper.scrape_pool_schedule(4151) # Incomplete matches (tournament so will always be like that)
        sch3 = self.scraper.scrape_pool_schedule(3934) # One match-up is at one location
        sch4 = self.scraper.scrape_pool_schedule(3486) # Each match-up has three games

        mtx1 = result_matrix(sch1)
        mtx2 = result_matrix(sch2)
        mtx3 = result_matrix(sch3)
        mtx4 = result_matrix(sch4)

        pass

    def test_pokalturnering_order(self):
        leagues = self.repo.get_leagues()
        bracket_leagues = pokal_filter(leagues)

        bracket_leagues['round'] = bracket_leagues.groupby(
            by=['gender', 'season']
        )['name'].apply(order_tournament).droplevel(['gender', 'season'])

        bracket_leagues = bracket_leagues.sort_values(['season', 'gender', 'round'])

        pass

    def test_slutspil_order(self):
        leagues = self.repo.get_leagues()
        bracket_leagues = slutspil_filter(leagues)

        bracket_leagues['round']= bracket_leagues.groupby(
            by=['gender', 'season']
        )['name'].apply(order_tournament).droplevel(['gender', 'season'])

        bracket_leagues = bracket_leagues.sort_values(['season', 'gender', 'round'])

        pass

    def test_deduct_tournament(self):
        district = 'Volleyball Danmark'
        season = 2025
        gender = 'Mand'
        leagues = self.repo.get_leagues()
        leagues = leagues.loc[leagues['season'].eq(season) & leagues['gender'].eq(gender) & leagues['district'].eq(district)]

        bracket_leagues = slutspil_filter(leagues)
        bracket_leagues['round'] = order_tournament(bracket_leagues['name'])

        matches = pd.read_sql(
            sql=f"""
                SELECT x.*, z.id as [league_id], z.name as [name_league]
                FROM matches x
                JOIN pools y
                JOIN leagues z
                ON x.pool_id=y.id and y.league_id=z.id
                WHERE z.id in ({', '.join(map(str,bracket_leagues['id'].to_list()))})
            """,
            con=self.repo.connection
        )

        df = matches.join(
            other=bracket_leagues.set_index('id')[['round']],
            on='league_id'
        )[['round', 'name_league', 'match_number', 'home_team', 'away_team', 'home_sets', 'away_sets']]

        tournament = deduct_tournament(df)
        pass


if __name__ == "__main__":
    unittest.main()
