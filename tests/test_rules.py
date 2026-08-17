from __future__ import annotations

from datetime import datetime
import unittest

from volleyball_resultater.models import Match, SetResult
from volleyball_resultater.rules import (
    HISTORIC_TWO_ONE_RULES,
    VOLLEYLIGAEN_2025_RULES,
    computed_standings,
    cumulative_points,
    match_points,
    result_matrix,
    rules_for_division,
)


class RulesTests(unittest.TestCase):
    def test_division_match_points(self) -> None:
        self.assertEqual(match_points(3, 0), (3, 0))
        self.assertEqual(match_points(3, 1), (3, 0))
        self.assertEqual(match_points(3, 2), (3, 1))
        self.assertEqual(match_points(2, 3), (1, 3))

    def test_volleyligaen_match_points(self) -> None:
        self.assertEqual(match_points(3, 2, VOLLEYLIGAEN_2025_RULES), (2, 1))
        self.assertEqual(match_points(2, 3, VOLLEYLIGAEN_2025_RULES), (1, 2))
        self.assertEqual(rules_for_division("Volleyligaen").id, "dt_2025_volleyligaen")
        self.assertEqual(rules_for_division("2. Division").id, "dt_2025_division")

    def test_historic_five_set_points(self) -> None:
        self.assertEqual(match_points(3, 2, HISTORIC_TWO_ONE_RULES), (2, 1))

    def test_ranking_uses_set_difference_before_games_won(self) -> None:
        matches = []
        kamp_id = 1
        for _ in range(6):
            matches.append(Match("pool", kamp_id, kamp_id, datetime(2025, 10, kamp_id, 19, 0), "Skive", f"Skive opponent {kamp_id}", "Hal", "1", 3, 0))
            kamp_id += 1
        for _ in range(3):
            matches.append(Match("pool", kamp_id, kamp_id, datetime(2025, 10, kamp_id, 19, 0), f"Skive opponent {kamp_id}", "Skive", "Hal", "1", 3, 2))
            kamp_id += 1
        for _ in range(7):
            matches.append(Match("pool", kamp_id, kamp_id, datetime(2025, 10, kamp_id, 19, 0), "SKF", f"SKF opponent {kamp_id}", "Hal", "1", 3, 1))
            kamp_id += 1
        for _ in range(9):
            matches.append(Match("pool", kamp_id, kamp_id, datetime(2025, 10, 28, 19, 0), f"SKF opponent {kamp_id}", "SKF", "Hal", "1", 3, 0))
            kamp_id += 1
        standings = computed_standings("pool", matches, [])
        positions = {row.team_name: row.rank for row in standings}
        self.assertLess(positions["Skive"], positions["SKF"])
        self.assertEqual(next(row for row in standings if row.team_name == "Skive").points, 21)
        self.assertEqual(next(row for row in standings if row.team_name == "SKF").points, 21)
        self.assertLess(
            next(row for row in standings if row.team_name == "Skive").games_won,
            next(row for row in standings if row.team_name == "SKF").games_won,
        )

    def test_computed_standings_and_outputs(self) -> None:
        matches = [
            Match("pool", 1, 1001, datetime(2025, 10, 1, 19, 0), "A", "B", "Hal", "1", 3, 2),
            Match("pool", 2, 1002, datetime(2025, 10, 2, 19, 0), "B", "A", "Hal", "1", 0, 3),
        ]
        sets = [
            SetResult(1, 1, 25, 20, 1, 0),
            SetResult(1, 2, 22, 25, 0, 1),
            SetResult(1, 3, 25, 21, 1, 0),
            SetResult(1, 4, 19, 25, 0, 1),
            SetResult(1, 5, 15, 12, 1, 0),
            SetResult(2, 1, 20, 25, 0, 1),
            SetResult(2, 2, 21, 25, 0, 1),
            SetResult(2, 3, 22, 25, 0, 1),
        ]
        standings = computed_standings("pool", matches, sets)
        self.assertEqual(standings[0].team_name, "A")
        self.assertEqual(standings[0].points, 6)
        self.assertEqual(standings[1].points, 1)

        events = cumulative_points(matches)
        self.assertEqual([event["cumulative_points"] for event in events if event["team"] == "A"], [0, 3, 6])

        matrix = result_matrix(matches)
        self.assertEqual(matrix["A"]["B"], "3-2")
        self.assertEqual(matrix["B"]["A"], "0-3")


if __name__ == "__main__":
    unittest.main()
