from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from volleyball_resultater.exporter import export_json
from volleyball_resultater.models import League, Pool, Season
from volleyball_resultater.storage import Repository


class ExporterTests(unittest.TestCase):
    def test_merge_existing_export_preserves_historical_seasons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_dir = root / "json"
            export_dir.mkdir()
            write_existing_export(export_dir)

            repo = Repository(root / "current.sqlite")
            try:
                repo.save_season(Season("2026", "Nuværende", "0", 2026, True))
                repo.save_league(League("2026:men:1-division", "2026", "Mand", "1. Division", "1. Division Herrer", 2371))
                repo.save_pool(Pool("2026_new_pool", "2026:men:1-division", "Øst", 4118))
                repo.commit()
            finally:
                repo.close()

            export_json(root / "current.sqlite", export_dir, merge_existing=True)

            merged = json.loads((export_dir / "leagues.json").read_text(encoding="utf-8"))
            self.assertEqual({league["season_id"] for league in merged["leagues"]}, {"2025", "2026"})
            self.assertEqual({pool["id"] for pool in merged["pools"]}, {"2025_pool", "2026_new_pool"})
            self.assertEqual(merged["metadata"]["seasons"], ["2026", "2025"])
            self.assertEqual(merged["metadata"]["league_count"], 2)
            self.assertEqual(merged["metadata"]["pool_count"], 2)
            self.assertTrue((export_dir / "2025_pool.json").exists())
            self.assertTrue((export_dir / "2026_new_pool.json").exists())
            self.assertFalse((export_dir / "2026_old_pool.json").exists())


def write_existing_export(export_dir: Path) -> None:
    (export_dir / "leagues.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "schema_version": 1,
                    "exported_at": "2026-09-01T00:00:00+02:00",
                    "scraper_version": "1.0.2",
                    "seasons": ["2026", "2025"],
                    "league_count": 2,
                    "pool_count": 2,
                    "validation": {"pools_with_mismatches": 0, "mismatch_count": 0},
                },
                "leagues": [
                    {
                        "id": "2026:men:1-division",
                        "season_id": "2026",
                        "gender": "Mand",
                        "division": "1. Division",
                        "name": "1. Division Herrer",
                        "raekke_id": 2371,
                    },
                    {
                        "id": "2025:men:1-division",
                        "season_id": "2025",
                        "gender": "Mand",
                        "division": "1. Division",
                        "name": "1. Division Herrer",
                        "raekke_id": 2251,
                    },
                ],
                "pools": [
                    {
                        "id": "2026_old_pool",
                        "league_id": "2026:men:1-division",
                        "name": "Øst",
                        "pulje_id": 4117,
                        "season_id": "2026",
                    },
                    {
                        "id": "2025_pool",
                        "league_id": "2025:men:1-division",
                        "name": "Øst",
                        "pulje_id": 3925,
                        "season_id": "2025",
                    },
                ],
                "pool_validation": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (export_dir / "2025_pool.json").write_text("{}", encoding="utf-8")
    (export_dir / "2026_old_pool.json").write_text("{}", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
