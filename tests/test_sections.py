"""Tests for the code-written sections of website reports (2-8 and 10), on the tiny fake dataset."""

from tennis_scout.facts import build_facts
from tennis_scout.headlines import write_sections
from tennis_scout.report import assemble_report, check_report, gather_report_data
from tennis_scout.sections import render_sections

ALPHA, BRAVO, CHARLIE = "atp-1", "atp-2", "atp-3"


def full_report(data, reply_text='{"summary": [], "takeaways": []}'):
    """A whole website report, the way the website builds it (here with plain code-written headlines)."""
    facts = build_facts(data)
    model_sections, _ = write_sections(data, facts, reply_text)
    return assemble_report({**render_sections(data), **model_sections})


def test_code_sections_hold_the_tool_numbers_and_pass_the_check(fake_db):
    data = gather_report_data(ALPHA, coach=BRAVO, db_path=fake_db)
    sections = render_sections(data)
    assert sorted(sections) == [2, 3, 4, 5, 6, 7, 8, 10]
    # Hand-computed in test_stats.py: Alpha's 1st serve in is 86 / 140 = 61.4%, over 2 used matches.
    assert "| 1st serve in | 61.4% |" in sections[2]
    assert "2 of 4 matches used. Excluded: 1 walkover, 1 retired or ended early" in sections[2]
    assert "**Small sample:** fewer than 10 matches." in sections[2]  # fake players have very few matches
    assert "**Wins:** Alpha Ace 2, Bravo Base 1" in sections[6]
    assert "2 matches went to a deciding set" in sections[6]
    assert "not results of matches between the two players" in sections[7]
    assert "Bravo Base's own serve" in sections[7]
    assert "<details><summary>Show Bravo Base's own serve and return numbers</summary>" in sections[7]
    assert '<span class="nowrap">6-3 2-1 RET</span>' in sections[6]  # a score never splits across two lines
    assert "<details>" not in sections[2]  # no surface chosen: there is no all-surface table to fold
    assert "Next Gen Finals" not in sections[4]  # Alpha played none: the reason is not mentioned
    assert "no usable stats" not in sections[2]  # none for Alpha either
    assert "(Alpha Ace, all surfaces, based on the percentiles)" in sections[5]
    assert "Licence: CC BY-NC-SA 4.0" in sections[10]
    assert check_report(full_report(data), data) == {"passed": True, "numbers_not_found": [], "problems": []}


def test_without_a_coach_and_without_meetings(fake_db):
    alone = render_sections(gather_report_data(ALPHA, db_path=fake_db))
    assert alone[6].endswith("No opponent given.") and alone[7].endswith("No opponent given.")

    # Alpha and Charlie never met, and Charlie has no usable serve stats: the report still builds and passes.
    never = gather_report_data(ALPHA, coach=CHARLIE, db_path=fake_db)
    assert "No meetings between Alpha Ace and Charlie Clay since 2015" in render_sections(never)[6]
    assert check_report(full_report(never), never)["passed"]


def test_the_all_surface_comparison_is_folded(fake_db):
    sections = render_sections(gather_report_data(ALPHA, coach=BRAVO, surface="Hard", db_path=fake_db))
    folded = "<details><summary>Show the all-surface numbers, for comparison</summary>"
    for number in (2, 3, 4):  # serve, return, pressure: the chosen surface stays open, all surfaces is folded
        assert sections[number].count(folded) == 1
        assert sections[number].index("hard,") < sections[number].index(folded)
