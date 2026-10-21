"""Where the database lives, how to open it, and the name-cleaning rule shared by build and search."""

import os
import sqlite3
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The database path can be changed with an environment variable (useful for tests and deployment).
DB_PATH = Path(os.environ.get("TENNIS_SCOUT_DB", PROJECT_ROOT / "data" / "tennis.db"))


def connect(path=None):
    """Open the database read-only, so the stats tools can never change the data."""
    path = Path(path or DB_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found at {path}. Run scripts/download_data.py then scripts/build_db.py."
        )
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row  # lets us read columns by name: row["name"]
    return connection


def normalize_name(text):
    """Lowercase and remove accents, so 'Świątek' and 'swiatek' match."""
    without_accents = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(without_accents.lower().replace("-", " ").split())
