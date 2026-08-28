from __future__ import annotations

import unittest

from volleyball_resultater.client import FIELD_SEASON, FetchResult
from volleyball_resultater.scraper import VolleyballScraper, regular_season_division


class FakeClient:
    def __init__(self, html: str, pages: dict[str, FetchResult] | None = None) -> None:
        self.html = html
        self.pages = pages or {}

    def initial_search_page(self) -> FetchResult:
        return FetchResult(url="https://example.test/search", html=self.html)

    def get(self, path: str) -> FetchResult:
        return self.pages[path]


class ScraperTests(unittest.TestCase):
    def test_current_season_uses_newest_numeric_year(self) -> None:
        scraper = VolleyballScraper(
            FakeClient(
                f"""
                <form>
                  <select name="{FIELD_SEASON}">
                    <option value="0">Nuværende</option>
                    <option value="2026">2026</option>
                    <option value="2025">2025</option>
                  </select>
                </form>
                """
            )
        )

        seasons = scraper.seasons()

        self.assertEqual(seasons[0].id, "2026")
        self.assertEqual(seasons[0].label, "Nuværende")
        self.assertEqual(seasons[0].value, "0")
        self.assertEqual(seasons[0].start_year, 2026)
        self.assertTrue(seasons[0].is_current)
        self.assertEqual([season.id for season in seasons], ["2026", "2025"])

    def test_volleyligaen_matching_is_case_insensitive(self) -> None:
        self.assertEqual(regular_season_division("Volleyligaen Herrer", "Mand"), "Volleyligaen")
        self.assertEqual(regular_season_division("VolleyLigaen Herrer", "Mand"), "Volleyligaen")
        self.assertEqual(regular_season_division("VolleyLigaen Kvinder", "Kvinde"), "Volleyligaen")

    def test_volleyligaen_playoffs_are_not_regular_season(self) -> None:
        self.assertIsNone(regular_season_division("VolleyLigaen Herrer DM Finaler", "Mand"))
        self.assertIsNone(regular_season_division("Volleyligaen Kvinder Bronze", "Kvinde"))

    def test_numbered_divisions_still_match_exactly(self) -> None:
        self.assertEqual(regular_season_division("1. Division Herrer", "Mand"), "1. Division")
        self.assertIsNone(regular_season_division("1. Division Herrer Kvalifikation", "Mand"))


if __name__ == "__main__":
    unittest.main()
