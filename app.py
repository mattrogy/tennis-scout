"""Vercel's entrypoint: Vercel looks for a variable named `app` in app.py at the project root.

The real website app is in src/tennis_scout/web.py; this file only points to it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))  # works whether or not the package is installed

from tennis_scout.web import app  # noqa: E402,F401
