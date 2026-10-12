from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "volleyball.sqlite"
DEFAULT_DB_PATH_NEW = PROJECT_ROOT / "data" / "volleyball_new.sqlite"
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "data" / "json"
DEFAULT_EXPORT_DIR_NEW = PROJECT_ROOT / "data" / "json_new"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw-html"
