from __future__ import annotations

import unittest

from volleyball_resultater.cli import season_matches
from volleyball_resultater.models import Season


class CliTests(unittest.TestCase):
    def test_current_season_matches_year_and_current_labels(self) -> None:
        season = Season("2026", "Nuværende", "0", 2026, True)

        self.assertTrue(season_matches(season, {"2026"}))
        self.assertTrue(season_matches(season, {"current"}))
        self.assertTrue(season_matches(season, {"Nuværende"}))


if __name__ == "__main__":
    unittest.main()
