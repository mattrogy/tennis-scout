"""Tests for the shared report module: which tools a report relies on, and who it is written for.

They use the tiny fake dataset from conftest.py, so they run without the real database.
"""

import pytest

from tennis_scout import stats
from tennis_scout.report import (PERIOD, REPORT_RULES, SECTION_HEADINGS, REPORT_SECTIONS, WEBSITE_RULES,
                                 assemble_report, build_messages, check_report, gather_report_data, perspective,
                                 report_rules)
from tennis_scout.sections import render_sections

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


def test_messages_carry_the_rules_the_perspective_and_the_sections(fake_db):
    data = gather_report_data(ALPHA, coach=BRAVO, surface="Clay", db_path=fake_db)
    sections = render_sections(data)
    system, user = build_messages(data, sections)
    assert system == {"role": "system", "content": WEBSITE_RULES}
    assert "Tactical takeaways for <coach's player>" in system["content"]
    assert "not results between these two players" in system["content"]
    assert user["content"].startswith("The coach's player is Bravo Base. The player being scouted is Alpha Ace.")
    assert "Surface: Clay." in user["content"]
    # The model reads the code-written sections, not raw JSON, and never sees section 1 or 9.
    for number in (2, 3, 4, 5, 6, 7, 8, 10):
        assert sections[number] in user["content"]
    assert "## 1." not in user["content"] and "## 9." not in user["content"]


def test_rules_are_built_from_the_period():
    assert REPORT_RULES == report_rules(PERIOD)
    fake_period = {"date_from": "2023-08-01", "date_to": "2025-07-07", "label": "August 2023 – July 2025"}
    rules = report_rules(fake_period)
    assert "August 2023 – July 2025 (date_from=2023-08-01, date_to=2025-07-07)" in rules
    assert "10. Data caveats" in rules
    # Rules added after the Mistral Small 4 check (DECISIONS.md): each one answers an error seen in a real report.
    assert "For the latest meeting, use most_recent_meeting" in rules
    assert "There is no ranking per surface" in rules
    assert "Never put a value from one answer next to a label or a match count from another" in rules
    assert 'write "small sample" next to its numbers' in rules
    assert "Do not give advice about shots or patterns that no number shows" in rules
    assert "A weak return number for the coach's player is a risk, not a plan" in rules
    assert 'Do not turn it into a rank or a group' in rules


# ---------------------------------------------------------------- check_report (hand-written reports)

ANSWERS = {
    "scouted_player": {"name": "Carlos Alcaraz"},
    "coach_player": {"name": "Jannik Sinner"},
    "period": {"date_from": "2024-06-01", "date_to": "2026-05-25"},
    "tool_answers": [{"tool": "serve_stats", "answer": {
        "serve": {"first_serve_points_won_pct": 69.4, "second_serve_points_won_pct": 55.0},
        "compared_to_tour": {"first_serve_points_won_pct": {"percentile": 99, "peers": 108}},
        "matches_used": 34,
        "points": 9960,
        "score": "6-4 7-5",  # scores are not a source of numbers
    }}],
}


def numbers_not_found(text, data=ANSWERS):
    return check_report(text, data)["numbers_not_found"]


def test_ordinal_stat_names_are_not_numbers():
    # "1st serve" and "2nd serve" are names: no invented 1 or 2.
    assert numbers_not_found("1st serve points won 69.4% (34 matches)") == []
    assert numbers_not_found("2nd serve points won 55.0%, and 1st-serve points 69.4%") == []


def test_invented_numbers_are_caught_even_next_to_ordinals():
    assert numbers_not_found("1st serve points won 71.2% (34 matches)") == ["71.2"]
    assert numbers_not_found("99th percentile of 108 players") == []
    assert numbers_not_found("12th percentile of 108 players") == ["12th"]
    assert numbers_not_found("3rd serve") == ["3rd"]  # only 1st and 2nd serve are stat names


def test_number_formats():
    assert numbers_not_found("9,960 points, period 2024-06-01 to 2026-05-25") == []
    assert numbers_not_found("9 960 points (9\u202f960 with a narrow space)") == []
    assert numbers_not_found("from 2024-07-01") == ["2024-07-01"]
    # Numbers inside a score are not accepted as a source: the rules forbid decoding scores.
    assert numbers_not_found("he won 7 games in the second set") == ["7"]
    # Copying the score exactly as the tool gives it is allowed.
    assert numbers_not_found("Lost 6-4 7-5 in the final") == []
    # List markers and the licence version are not numbers to check; R16 is a round, not a number.
    assert numbers_not_found("## 3. Return\n1. Lost in the R16\nData: CC BY-NC-SA 4.0, since 2015") == []


def full_report(takeaways_for="Sinner", sections=SECTION_HEADINGS, opponent_text="Alcaraz leads 34 matches."):
    lines = []
    for number, heading in enumerate(sections, start=1):
        lines.append(f"## {number}. {heading}" + (f" for {takeaways_for}" if heading == "Tactical takeaways" else ""))
        lines.append(opponent_text if heading in ("Head-to-head", "Matchup") else "1st serve points won 69.4%.")
    return "\n".join(lines)


def test_a_good_report_passes():
    assert len(SECTION_HEADINGS) == len(REPORT_SECTIONS)
    assert check_report(full_report(), ANSWERS) == {"passed": True, "numbers_not_found": [], "problems": []}
    # Bold headings and "Head to head" without hyphens are accepted too.
    bold = full_report().replace("## 6. Head-to-head", "**6. Head to head**")
    assert check_report(bold, ANSWERS)["passed"]


def test_blank_lines_between_sections():
    # Real reports leave a blank line before each heading: the heading must still be read as its own line.
    spaced = full_report().replace("\n## ", "\n\n## ")
    assert check_report(spaced, ANSWERS)["passed"]
    assert check_report(spaced.replace("for Sinner", "for Alcaraz"), ANSWERS)["problems"] == [
        "The takeaways heading does not name the coach's player (Jannik Sinner)."]


def test_missing_or_misordered_sections_fail():
    without_pressure = [h for h in SECTION_HEADINGS if h != "Pressure"]
    result = check_report(full_report(sections=without_pressure), ANSWERS)
    assert not result["passed"]
    assert "Missing section: Pressure." in result["problems"]

    swapped = full_report().replace("## 2. Serve", "## X").replace("## 3. Return", "## 2. Serve")
    swapped = swapped.replace("## X", "## 3. Return")
    assert "The sections are not in the expected order." in check_report(swapped, ANSWERS)["problems"]


def test_wrong_camp_fails():
    result = check_report(full_report(takeaways_for="Alcaraz"), ANSWERS)
    assert result["problems"] == ["The takeaways heading does not name the coach's player (Jannik Sinner)."]


def test_without_a_coach_head_to_head_and_matchup_say_so():
    alone = {**ANSWERS, "coach_player": None}
    assert check_report(full_report(opponent_text="No opponent given."), alone)["passed"]
    result = check_report(full_report(), alone)
    assert result["problems"] == ['Head-to-head should say "No opponent given."',
                                  'Matchup should say "No opponent given."']


def test_stretch_and_shot_words_are_flagged_in_summary_and_takeaways_only():
    report = full_report().replace("## 9. Tactical takeaways for Sinner\n1st serve points won 69.4%.",
                                   "## 9. Tactical takeaways for Sinner\nAn elite server: hit deep returns, only 69.4%.")
    report += "\nThese stats cannot show rally length or net play."  # in the Data caveats: allowed
    problems = check_report(report, ANSWERS)["problems"]
    assert problems == [
        "Tactical takeaways uses 'elite', 'only 69.4%': percentiles must be written as \"Nth percentile of P players\".",
        "Tactical takeaways uses 'deep': the data cannot show shots or patterns.",
    ]
