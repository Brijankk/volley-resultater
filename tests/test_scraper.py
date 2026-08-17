from __future__ import annotations

import unittest

from volleyball_resultater.scraper import regular_season_division


class ScraperTests(unittest.TestCase):
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
