from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from volleyball_resultater.models import League, Pool, Season, StandingRow
from volleyball_resultater.storage import Repository
from volleyball_resultater.validation import validate_rankings, validation_summary


class ValidationTests(unittest.TestCase):
    def test_matching_rankings_have_no_mismatches(self) -> None:
        with temp_repo() as repo:
            seed_pool(repo)
            row = standing("pool", 1, "A", points=10)
            repo.replace_source_standings("pool", [row])
            repo.replace_computed_standings("pool", "five_set_3_1", [row])
            repo.commit()

            self.assertEqual(validate_rankings(repo.connection), [])

    def test_mismatch_reports_field_difference(self) -> None:
        with temp_repo() as repo:
            seed_pool(repo)
            repo.replace_source_standings("pool", [standing("pool", 1, "A", points=10)])
            repo.replace_computed_standings("pool", "five_set_3_1", [standing("pool", 1, "A", points=9)])
            repo.commit()

            mismatches = validate_rankings(repo.connection)
            self.assertEqual(len(mismatches), 1)
            self.assertEqual(mismatches[0].team_name, "A")
            self.assertEqual(mismatches[0].field, "points")
            self.assertEqual(mismatches[0].official, 10)
            self.assertEqual(mismatches[0].computed, 9)

            summary = validation_summary(repo.connection)
            self.assertEqual(summary["pool"].mismatch_count, 1)
            self.assertEqual(summary["pool"].affected_teams, 1)
            self.assertEqual(summary["pool"].affected_fields, ["points"])


def temp_repo():
    class TempRepo:
        def __enter__(self) -> Repository:
            self.directory = tempfile.TemporaryDirectory()
            self.repo = Repository(Path(self.directory.name) / "test.sqlite")
            return self.repo

        def __exit__(self, exc_type, exc, tb) -> None:
            self.repo.close()
            self.directory.cleanup()

    return TempRepo()


def seed_pool(repo: Repository) -> None:
    repo.save_season(Season("2025", "2025", "2025", 2025, False))
    repo.save_league(League("league", "2025", "Mand", "2. Division", "2. Division Herrer", 2251))
    repo.save_pool(Pool("pool", "league", "Nord", 3929))


def standing(pool_id: str, rank: int, team: str, points: int) -> StandingRow:
    return StandingRow(
        pool_id=pool_id,
        rank=rank,
        team_name=team,
        games_played=1,
        games_won=1,
        games_lost=0,
        sets_won=3,
        sets_lost=0,
        balls_won=75,
        balls_lost=50,
        points=points,
    )


if __name__ == "__main__":
    unittest.main()
