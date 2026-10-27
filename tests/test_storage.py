from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
import unittest

from volleyball_resultater.storage import Repository


class StorageSchemaTests(unittest.TestCase):
    def test_legacy_identifier_columns_are_renamed_and_data_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "legacy.sqlite"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE leagues (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, district TEXT NOT NULL,
                    gender TEXT NOT NULL, age_group TEXT NOT NULL, season INTEGER NOT NULL
                );
                CREATE TABLE pools (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    league_id INTEGER NOT NULL REFERENCES leagues(id)
                );
                CREATE TABLE rankings (
                    pool_id INTEGER NOT NULL REFERENCES pools(id), team_name TEXT NOT NULL,
                    PRIMARY KEY (pool_id, team_name)
                );
                CREATE TABLE matches (
                    pool_id INTEGER NOT NULL REFERENCES pools(id), id INTEGER PRIMARY KEY,
                    home_team TEXT NOT NULL, away_team TEXT NOT NULL
                );
                INSERT INTO leagues VALUES (7, 'Volleyligaen Herrer', 'Volleyball Danmark', 'Mand', 'Senior', 2025);
                INSERT INTO pools VALUES (42, 'Øst', 7);
                INSERT INTO rankings VALUES (42, 'Hold A');
                INSERT INTO matches VALUES (42, 1234, 'Hold A', 'Hold B');
                """
            )
            connection.close()

            repository = Repository(database)
            try:
                self.assertEqual(
                    [row[1] for row in repository.connection.execute("PRAGMA table_info(leagues)")],
                    ["league_id", "league_name", "district", "gender", "age_group", "season"],
                )
                self.assertEqual(
                    [row[1] for row in repository.connection.execute("PRAGMA table_info(pools)")],
                    ["pool_id", "pool_name", "league_id"],
                )
                self.assertIn(
                    "match_id",
                    [row[1] for row in repository.connection.execute("PRAGMA table_info(matches)")],
                )
                self.assertEqual(
                    tuple(repository.connection.execute(
                        "SELECT league_id, league_name FROM leagues"
                    ).fetchone()),
                    (7, "Volleyligaen Herrer"),
                )
                self.assertEqual(
                    tuple(repository.connection.execute(
                        "SELECT pool_id, pool_name, league_id FROM pools"
                    ).fetchone()),
                    (42, "Øst", 7),
                )
                self.assertEqual(
                    tuple(repository.connection.execute(
                        "SELECT pool_id, match_id FROM matches"
                    ).fetchone()),
                    (42, 1234),
                )
                self.assertEqual(repository.connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(repository.get_leagues().columns[0:2].tolist(), ["league_id", "league_name"])
            finally:
                repository.close()

            # Opening an already migrated database is safe and idempotent.
            repository = Repository(database)
            repository.close()


if __name__ == "__main__":
    unittest.main()
