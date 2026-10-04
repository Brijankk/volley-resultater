from __future__ import annotations

import unittest

from volleyball_resultater.client import FIELD_SEASON, FetchResult
from volleyball_resultater.models import Season
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
    def test_current_season_uses_newest_numeric_year_plus_one(self) -> None:
        scraper = VolleyballScraper(
            FakeClient(
                f"""
                <form>
                  <select name="{FIELD_SEASON}">
                    <option value="0">Nuværende</option>
                    <option value="2025">2025</option>
                    <option value="2024">2024</option>
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
        self.assertEqual([season.id for season in seasons], ["2026", "2025", "2024"])
        self.assertEqual(seasons[1].value, "2025")
        self.assertFalse(seasons[1].is_current)

    def test_current_season_assumption_applies_when_newer_year_is_listed(self) -> None:
        scraper = VolleyballScraper(FakeClient(f"""
            <form><select name="{FIELD_SEASON}">
                <option value="0">Nuværende</option>
                <option value="2025">2025</option>
                <option value="2026">2026</option>
            </select></form>
        """))

        seasons = scraper.seasons()

        self.assertEqual([season.id for season in seasons], ["2027", "2025", "2026"])
        self.assertEqual(seasons[0].start_year, 2027)
        self.assertEqual(seasons[0].value, "0")

    def test_current_season_without_numbered_years_keeps_unknown_year(self) -> None:
        scraper = VolleyballScraper(FakeClient(f"""
            <form><select name="{FIELD_SEASON}">
                <option value="0">Nuværende</option>
            </select></form>
        """))

        self.assertEqual(scraper.seasons(), [Season("current", "Nuværende", "0", None, True)])

    def test_numbered_seasons_without_current_option_are_preserved(self) -> None:
        scraper = VolleyballScraper(FakeClient(f"""
            <form><select name="{FIELD_SEASON}">
                <option value="2025">2025</option>
                <option value="2024">2024</option>
            </select></form>
        """))

        self.assertEqual(scraper.seasons(), [
            Season("2025", "2025", "2025", 2025, False),
            Season("2024", "2024", "2024", 2024, False),
        ])

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
