"""Tests for the shared report module: which tools a report relies on, and who it is written for.

They use the tiny fake dataset from conftest.py, so they run without the real database.
"""

import pytest

from tennis_scout import stats
from tennis_scout.report import REPORT_RULES, PERIOD, perspective, report_rules, gather_report_data

ALPHA, BRAVO, ZOE = "atp-1", "atp-2", "wta-10"


def tools_called(data):
    return [entry["tool"] for entry in data["tool_answers"]]


def test_report_with_coach_and_surface(fake_db):
    data = gather_report_data(ALPHA, coach=BRAVO, surface="Clay", db_path=fake_db)
    assert tools_called(data) == [
        "serve_stats", "return_stats", "pressure_stats",   # Alpha on clay
        "serve_stats", "return_stats", "pressure_stats",   # Alpha on all surfaces, to compare
        "head_to_head", "matchup",
        "serve_stats", "return_stats",                     # Bravo, the coach's player
        "recent_form",
    ]
    period = stats.default_report_period(fake_db)
    dates = {"date_from": period["date_from"], "date_to": period["date_to"]}
    arguments = [entry["arguments"] for entry in data["tool_answers"]]
    assert arguments[0] == {"player": ALPHA, "surface": "Clay", **dates}
    assert arguments[3] == {"player": ALPHA, **dates}                              # no surface filter
    assert arguments[6] == {"player_a": ALPHA, "player_b": BRAVO, "surface": "Clay"}  # no dates: all meetings
    assert arguments[7] == {"player": ALPHA, "opponent": BRAVO, "surface": "Clay", **dates}
    assert arguments[8] == {"player": BRAVO, "surface": "Clay", **dates}
    assert arguments[10] == {"player": ALPHA, "n": 10}

    assert data["scouted_player"]["name"] == "Alpha Ace"
    assert data["coach_player"]["name"] == "Bravo Base"
    assert data["period"] == period
    assert data["perspective"].startswith("The coach's player is Bravo Base. The player being scouted is Alpha Ace.")
    # The answers are the tools' own answers, untouched.
    assert data["tool_answers"][0]["answer"] == stats.serve_stats(ALPHA, surface="Clay", db_path=fake_db, **dates)


def test_report_without_coach_or_surface(fake_db):
    data = gather_report_data(ALPHA, db_path=fake_db)
    # No surface: the "all surfaces" comparison would repeat the same calls, so it is skipped.
    assert tools_called(data) == ["serve_stats", "return_stats", "pressure_stats", "recent_form"]
    assert data["coach_player"] is None
    assert data["perspective"] == perspective("Alpha Ace")
    assert "preparing a match against Alpha Ace" in data["perspective"]


def test_report_refuses_bad_pairs(fake_db):
    with pytest.raises(stats.StatsError, match="two different players"):
        gather_report_data(ALPHA, coach=ALPHA, db_path=fake_db)
    with pytest.raises(stats.StatsError, match="different tours"):
        gather_report_data(ALPHA, coach=ZOE, db_path=fake_db)
    with pytest.raises(stats.StatsError, match="Use find_player first"):
        gather_report_data("atp-999", db_path=fake_db)
    with pytest.raises(stats.StatsError, match="Surface must be one of"):
        gather_report_data(ALPHA, surface="Carpet", db_path=fake_db)


def test_rules_are_built_from_the_period():
    assert REPORT_RULES == report_rules(PERIOD)
    fake_period = {"date_from": "2023-08-01", "date_to": "2025-07-07", "label": "August 2023 – July 2025"}
    rules = report_rules(fake_period)
    assert "August 2023 – July 2025 (date_from=2023-08-01, date_to=2025-07-07)" in rules
    assert "10. Data caveats" in rules
