from __future__ import annotations

import unittest

import pandas as pd

from volleyball_resultater.scraper import VolleyballScraper, DISTRICT, AGE_GROUP, GENDERS
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.paths import PROJECT_ROOT, DEFAULT_CACHE_DIR, DEFAULT_DB_PATH
from volleyball_resultater.wrangling import calculate_running_rankings, result_matrix, order_tournament, deduct_tournament


class WranglingTests(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        self.client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
        self.scraper = VolleyballScraper(self.client)

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

    def test_tournament_making(self):        
        # m1 = self.scraper.scrape_match_details(72486) # Full 5 sets
        # m2 = self.scraper.scrape_match_details(72482) # Only 3 sets
        # m3 = self.scraper.scrape_match_details(75954) # Match not played yet
        # m4 = self.scraper.scrape_match_details(72338) # Match has note
        # m5 = self.scraper.scrape_match_details(76523)

        # df = pd.concat([m1, m2, m3, m4, m5])

        pass

if __name__ == "__main__":
    unittest.main()
