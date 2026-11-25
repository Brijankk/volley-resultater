from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import pandas as pd

from volleyball_resultater.storage import Repository


class RepositoryTests(unittest.TestCase):
    def test_upserts_keep_current_schema_and_update_existing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "volleyball.sqlite"
            with Repository(database) as repository:
                league = pd.DataFrame({
                    "league_id": [7],
                    "league_name": ["Volleyligaen Herrer"],
                    "district": ["Volleyball Danmark"],
                    "gender": ["Mand"],
                    "age_group": ["Senior"],
                    "season": [2025],
                })
                repository.upsert_leagues(league)

                pool = pd.DataFrame({
                    "pool_id": [42],
                    "pool_name": ["Øst"],
                    "league_id": [7],
                })
                repository.upsert_pools(pool)

                ranking = pd.DataFrame({
                    "pool_id": [42],
                    "rank": [1],
                    "team_name": ["Hold A"],
                    "games_played": [4],
                    "games_won": [3],
                    "games_lost": [1],
                    "sets_won": [11],
                    "sets_lost": [6],
                    "balls_won": [390],
                    "balls_lost": [345],
                    "points": [9],
                })
                repository.upsert_rankings(ranking)

                league.loc[0, "league_name"] = "Volleyligaen"
                repository.upsert_leagues(league)
                repository.commit()

                leagues = repository.get_leagues()
                pools = repository.get_pools_with_leagues()
                rankings = repository.get_rankings()

                self.assertEqual(leagues.loc[0, "league_name"], "Volleyligaen")
                self.assertEqual((pools.loc[0, "pool_id"], pools.loc[0, "league_name"]), (42, "Volleyligaen"))
                self.assertEqual((rankings.loc[0, "team_name"], rankings.loc[0, "points"]), ("Hold A", 9))
                self.assertEqual(repository.connection.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
