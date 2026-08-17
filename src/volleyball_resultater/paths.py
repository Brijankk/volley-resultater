from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "volleyball.sqlite"
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "data" / "json"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw-html"
