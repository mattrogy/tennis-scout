"""Tests for the Vercel setup: the entrypoint Vercel loads, and the settings it reads."""

import importlib.util
import json
import tomllib

from tennis_scout import web
from tennis_scout.db import PROJECT_ROOT


def test_vercel_entrypoint_is_the_website_app():
    spec = importlib.util.spec_from_file_location("vercel_entrypoint", PROJECT_ROOT / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.app is web.app


def test_vercel_settings():
    settings = json.loads((PROJECT_ROOT / "vercel.json").read_text())
    function = settings["functions"]["app.py"]
    assert function["maxDuration"] == 60  # the model call times out at 50 s, the function at 60 s
    assert "data/raw/**" in function["excludeFiles"]  # the raw CSVs stay out of the function
    assert "tennis.db" not in function["excludeFiles"]  # the database must stay in

    build = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())["tool"]["vercel"]["scripts"]["build"]
    assert "download_data.py" in build and "build_db.py" in build  # the database is built during each deploy
