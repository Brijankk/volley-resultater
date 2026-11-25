from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from volleyball_resultater.exporter import export_json
from volleyball_resultater.paths import SCHEMA_PATH


class ExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.db_path = root / "volleyball.sqlite"
        self.output_dir = root / "json"
        self.config_path = root / "config.json"
        self.config_path.write_text(
            json.dumps({
                "league_filter": {
                    "union": [[{
                        "column": "district",
                        "type": "equal",
                        "value": "volleyball danmark",
                        "invert": False,
                    }]],
                    "intersect": [[{
                        "column": "season",
                        "type": ">=",
                        "value": 2021,
                        "invert": False,
                    }]],
                }
            }),
            encoding="utf-8",
        )
        self.connection = sqlite3.connect(self.db_path)
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def seed_pool(self) -> None:
        self.connection.execute(
            "INSERT INTO leagues VALUES (7, 'Volleyligaen Herrer', 'Volleyball Danmark', 'Mand', 'Senior', 2025)"
        )
        self.connection.execute("INSERT INTO pools VALUES (42, 'Øst', 7)")

    def add_match(
        self,
        *,
        match_id: int = 1,
        starts_at: str | None = "2025-10-04T00:00:00",
        home_sets: int | None = 3,
        away_sets: int | None = 2,
        home_points: int | None = 2,
        away_points: int | None = 1,
        note: str | None = None,
    ) -> None:
        self.connection.execute(
            """INSERT INTO matches (
                pool_id, match_id, match_number, match_time, home_team, away_team,
                venue, court, address, home_sets, away_sets, home_points, away_points,
                note, home_balls1, away_balls1
            ) VALUES (42, ?, ?, ?, 'A', 'B', 'Arena', '1', 'Street 1', ?, ?, ?, ?, ?, 25, 20)""",
            (match_id, 100 + match_id, starts_at, home_sets, away_sets,
             home_points, away_points, note),
        )

    def add_ranking(self, team: str, rank: int, points: int) -> None:
        won = int(team == "A")
        self.connection.execute(
            """INSERT INTO rankings (
                pool_id, rank, team_name, games_played, games_won, games_lost,
                sets_won, sets_lost, balls_won, balls_lost, points
            ) VALUES (42, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)""",
            (rank, team, won, 1 - won, 3 if won else 2, 2 if won else 3,
             25 if won else 20, 20 if won else 25, points),
        )

    def export(self) -> tuple[dict, dict]:
        self.connection.commit()
        before = self.db_path.read_bytes()
        export_json(self.db_path, self.output_dir, self.config_path)
        self.assertEqual(self.db_path.read_bytes(), before)
        index = json.loads((self.output_dir / "leagues.json").read_text(encoding="utf-8"))
        pool = json.loads((self.output_dir / "42.json").read_text(encoding="utf-8"))
        return index, pool

    def test_exports_the_current_frontend_contract(self) -> None:
        self.seed_pool()
        self.add_match()
        self.add_ranking("A", 1, 2)
        self.add_ranking("B", 2, 1)

        index, pool = self.export()

        self.assertEqual(index["leagues"][0]["id"], "7")
        self.assertEqual(index["leagues"][0]["name"], "Volleyligaen")
        self.assertEqual(index["leagues"][0]["season"], "2025")
        self.assertEqual(index["pools"][0]["id"], "42")
        self.assertEqual(index["pools"][0]["name"], "Indledende")
        self.assertEqual(pool["pool"]["league_name"], "Volleyligaen")
        self.assertIs(pool["metadata"]["validation"], True)
        self.assertEqual([row["team_name"] for row in pool["source_standings"]], ["A", "B"])

        match = pool["matches"][0]
        self.assertEqual(match["kamp_id"], 1)
        self.assertEqual(match["result_home_sets"], 3)
        self.assertEqual(match["result_away_sets"], 2)
        self.assertEqual(match["starts_at"], "2025-10-04T00:00:00")
        self.assertFalse(match["starts_at_time_known"])
        self.assertNotIn("match_id", match)

        final_points = {
            row["team"]: row["cumulative_points"]
            for row in pool["cumulative_points"]
            if row["game_number"] == 1
        }
        self.assertEqual(final_points, {"A": 2, "B": 1})
        self.assertEqual(pool["result_matrix"]["A"]["B"], "3-2")
        self.assertEqual(pool["result_matrix"]["B"]["A"], "")

    def test_reports_a_points_mismatch_without_recomputing_official_standings(self) -> None:
        self.seed_pool()
        self.add_match()
        self.add_ranking("A", 2, 3)
        self.add_ranking("B", 1, 1)

        index, pool = self.export()

        self.assertIs(pool["metadata"]["validation"], False)
        self.assertEqual(index["pool_validation"], {"42": False})
        self.assertEqual(pool["source_standings"][0]["team_name"], "B")
        self.assertEqual(pool["source_standings"][0]["points"], 1)

    def test_merge_keeps_unexported_history_and_its_pool_file(self) -> None:
        self.seed_pool()
        self.add_match()
        self.add_ranking("A", 1, 2)
        self.add_ranking("B", 2, 1)
        self.export()

        historic_file = self.output_dir / "41.json"
        historic_file.write_text('{"historic": true}\n', encoding="utf-8")
        historic_contents = historic_file.read_bytes()
        index_path = self.output_dir / "leagues.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["leagues"].append({
            "id": "6",
            "name": "Historic league",
            "district": "Volleyball Danmark",
            "gender": "Mand",
            "season": "2024",
            "age_group": "Senior",
            "backend_league_ids": [6],
        })
        index["pools"].append({
            "id": "41",
            "name": "Historic pool",
            "format": "Robin",
            "league_id": "6",
            "backend_pool_ids": [41],
        })
        index["pool_validation"]["41"] = False
        index_path.write_text(json.dumps(index), encoding="utf-8")

        merged, _ = self.export()

        self.assertEqual({row["id"] for row in merged["leagues"]}, {"6", "7"})
        self.assertEqual({row["id"] for row in merged["pools"]}, {"41", "42"})
        self.assertEqual(merged["pool_validation"], {"41": False})
        self.assertEqual(historic_file.read_bytes(), historic_contents)

    def test_invalid_existing_index_does_not_overwrite_pool_exports(self) -> None:
        self.seed_pool()
        self.add_match()
        self.add_ranking("A", 1, 2)
        self.add_ranking("B", 2, 1)
        self.connection.commit()
        self.output_dir.mkdir()
        index_path = self.output_dir / "leagues.json"
        pool_path = self.output_dir / "42.json"
        index_path.write_text("not json", encoding="utf-8")
        pool_path.write_text("previous pool data", encoding="utf-8")

        with self.assertRaises(ValueError):
            export_json(self.db_path, self.output_dir, self.config_path)

        self.assertEqual(index_path.read_text(encoding="utf-8"), "not json")
        self.assertEqual(pool_path.read_text(encoding="utf-8"), "previous pool data")


if __name__ == "__main__":
    unittest.main()
