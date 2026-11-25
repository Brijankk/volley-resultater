from __future__ import annotations

import unittest

import pandas as pd

from volleyball_resultater.wrangling import (
    calculate_running_points,
    deduct_bracket,
    frame_filter,
    order_tournament,
    result_matrix,
)


class WranglingTests(unittest.TestCase):
    def test_running_points_starts_at_zero_and_accumulates_scraped_points(self) -> None:
        matches = pd.DataFrame({
            "match_time": pd.to_datetime(["2025-10-01", "2025-10-08"]),
            "home_team": ["A", "A"],
            "away_team": ["B", "C"],
            "home_points": [2, 3],
            "away_points": [1, 0],
        })

        events = calculate_running_points(matches)
        team_a = events.loc[events["team"].eq("A")].sort_values("game_number")

        self.assertEqual(team_a["game_number"].tolist(), [0, 1, 2])
        self.assertEqual(team_a["cumulative_points"].tolist(), [0, 2, 5])
        self.assertTrue(pd.isna(team_a["match_time"].iloc[0]))

    def test_result_matrix_lists_played_results_and_omits_unplayed_fixtures(self) -> None:
        matches = pd.DataFrame({
            "home_team": ["A", "A", "B"],
            "away_team": ["B", "B", "A"],
            "home_sets": pd.array([3, 2, None], dtype="Int64"),
            "away_sets": pd.array([1, 3, None], dtype="Int64"),
        })

        matrix = result_matrix(matches)

        self.assertEqual(matrix.loc[("A", "B")], "3-1, 2-3")
        self.assertEqual(matrix.loc[("B", "A")], "")
        self.assertEqual(matrix.loc[("A", "A")], "")

    def test_tournament_rounds_are_ordered_from_opening_round_to_final(self) -> None:
        names = pd.Series([
            "1. Runde",
            "2. Runde",
            "Kvartfinale",
            "Semifinale",
            "Finale",
        ])

        rounds = order_tournament(names)

        self.assertLess(rounds.iloc[0], rounds.iloc[1])
        self.assertLess(rounds.iloc[1], rounds.iloc[2])
        self.assertLess(rounds.iloc[2], rounds.iloc[3])
        self.assertLess(rounds.iloc[3], rounds.iloc[4])

    def test_bracket_links_a_returning_team_to_its_previous_match(self) -> None:
        schedule = pd.DataFrame([
            {
                "round": 0,
                "league_name": "Pokalturneringen",
                "match_number": 11,
                "home_team": "A",
                "away_team": "B",
                "home_sets": 3,
                "away_sets": 0,
                "note": "",
            },
            {
                "round": 1,
                "league_name": "Pokalturneringen",
                "match_number": 12,
                "home_team": "A",
                "away_team": "C",
                "home_sets": 1,
                "away_sets": 3,
                "note": "",
            },
        ])

        bouts = deduct_bracket(schedule)

        self.assertEqual(len(bouts), 2)
        opening = bouts.loc[bouts["round"].eq(0)].iloc[0]
        final = bouts.loc[bouts["round"].eq(1)].iloc[0]
        self.assertEqual(opening["winner"], "A")
        self.assertEqual(final["winner"], "C")
        links = [value for value in (final["leg1"], final["leg2"]) if not pd.isna(value)]
        self.assertEqual(links, [0])

    def test_frame_filter_applies_union_and_intersection_conditions(self) -> None:
        leagues = pd.DataFrame({
            "district": ["Volleyball Danmark", "Midtjysk Volleyball", "Volleyball Danmark"],
            "season": [2025, 2025, 2020],
            "league_name": ["Volleyligaen", "1. Division", "Volleyligaen"],
        })
        config = {
            "union": [
                [{"column": "district", "type": "equal", "value": "volleyball danmark", "invert": False}],
                [{"column": "district", "type": "equal", "value": "midtjysk volleyball", "invert": False}],
            ],
            "intersect": [
                [{"column": "season", "type": ">=", "value": 2021, "invert": False}],
            ],
        }

        selected = frame_filter(leagues, config)

        self.assertEqual(set(selected["league_name"]), {"Volleyligaen", "1. Division"})
        self.assertNotIn(2020, selected["season"].tolist())


if __name__ == "__main__":
    unittest.main()
