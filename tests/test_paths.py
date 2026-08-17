from __future__ import annotations

import unittest

from volleyball_resultater.paths import DEFAULT_CACHE_DIR, DEFAULT_DB_PATH, DEFAULT_EXPORT_DIR, PROJECT_ROOT


class PathTests(unittest.TestCase):
    def test_default_paths_are_project_root_anchored(self) -> None:
        self.assertEqual(DEFAULT_DB_PATH, PROJECT_ROOT / "data" / "volleyball.sqlite")
        self.assertEqual(DEFAULT_EXPORT_DIR, PROJECT_ROOT / "data" / "json")
        self.assertEqual(DEFAULT_CACHE_DIR, PROJECT_ROOT / "data" / "raw-html")


if __name__ == "__main__":
    unittest.main()
