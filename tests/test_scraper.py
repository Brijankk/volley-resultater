from __future__ import annotations

import unittest

import pandas as pd

from volleyball_resultater.client import FIELD_SEASON, FetchResult
from volleyball_resultater.scraper import VolleyballScraper, DISTRICT, AGE_GROUP, GENDERS
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.paths import PROJECT_ROOT, DEFAULT_CACHE_DIR, DEFAULT_DB_PATH


class FakeClient:
    def __init__(self, html: str, pages: dict[str, FetchResult] | None = None) -> None:
        self.html = html
        self.pages = pages or {}

    def initial_search_page(self) -> FetchResult:
        return FetchResult(url="https://example.test/search", html=self.html)

    def get(self, path: str) -> FetchResult:
        return self.pages[path]


class ScraperTests(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        self.client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0, refresh_cache=False)
        self.scraper = VolleyballScraper(self.client)

        super().__init__(methodName)

    def test_get_seasons(self):
        seasons = self.scraper.get_seasons()

        pass

    def test_get_schedules(self):
        sch1 = self.scraper.scrape_pool_schedule(4124) # No matches played
        sch2 = self.scraper.scrape_pool_schedule(4151) # Incomplete matches
        sch3 = self.scraper.scrape_pool_schedule(4123) # Some matches miss starttime
        sch4 = self.scraper.scrape_pool_schedule(3927) # Some matches have notes

        sch = pd.concat([sch1, sch2, sch3, sch4])

        pass

    def test_get_matches(self):        
        m1 = self.scraper.scrape_match_details(72486) # Full 5 sets
        m2 = self.scraper.scrape_match_details(72482) # Only 3 sets
        m3 = self.scraper.scrape_match_details(75954) # Match not played yet
        m4 = self.scraper.scrape_match_details(72338) # Match has note
        m5 = self.scraper.scrape_match_details(76523)

        df = pd.concat([m1, m2, m3, m4, m5])

        pass

if __name__ == "__main__":
    unittest.main()
