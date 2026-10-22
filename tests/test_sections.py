"""Tests for the code-written sections of website reports (2-8 and 10), on the tiny fake dataset."""

from tennis_scout.report import assemble_report, check_report, gather_report_data
from tennis_scout.sections import render_sections

ALPHA, BRAVO, CHARLIE = "atp-1", "atp-2", "atp-3"


def model_reply(coach="the coach"):
    """What a well-behaved model sends back: only sections 1 and 9."""
    return f"## 1. Summary\n\n- A summary.\n\n## 9. Tactical takeaways for {coach}\n\n- A takeaway."


def test_code_sections_hold_the_tool_numbers_and_pass_the_check(fake_db):
    data = gather_report_data(ALPHA, coach=BRAVO, db_path=fake_db)
    sections = render_sections(data)
    assert sorted(sections) == [2, 3, 4, 5, 6, 7, 8, 10]
    # Hand-computed in test_stats.py: Alpha's 1st serve in is 86 / 140 = 61.4%, over 2 used matches.
    assert "| 1st serve in | 61.4% |" in sections[2]
    assert "2 of 4 matches used. Excluded: 1 walkover(s), 1 retired or ended early" in sections[2]
    assert "**Small sample:** fewer than 10 matches." in sections[2]  # fake players have very few matches
    assert "**Wins:** Alpha Ace 2, Bravo Base 1" in sections[6]
    assert "2 matches went to a deciding set" in sections[6]
    assert "not results of matches between the two players" in sections[7]
    assert "Bravo Base's own serve" in sections[7]
    assert "Licence: CC BY-NC-SA 4.0" in sections[10]

    report = assemble_report(sections, model_reply("Bravo Base"))
    assert check_report(report, data) == {"passed": True, "numbers_not_found": [], "problems": []}


def test_without_a_coach_and_without_meetings(fake_db):
    alone = render_sections(gather_report_data(ALPHA, db_path=fake_db))
    assert alone[6].endswith("No opponent given.") and alone[7].endswith("No opponent given.")

    # Alpha and Charlie never met, and Charlie has no usable serve stats: the sections still render.
    never = gather_report_data(ALPHA, coach=CHARLIE, db_path=fake_db)
    sections = render_sections(never)
    assert "No meetings between Alpha Ace and Charlie Clay since 2015" in sections[6]
    report = assemble_report(sections, model_reply("Charlie Clay"))
    assert check_report(report, never)["passed"]


def test_assemble_keeps_only_the_model_sections_it_should(fake_db):
    data = gather_report_data(ALPHA, coach=BRAVO, db_path=fake_db)
    sections = render_sections(data)
    # A model that also writes its own "Serve" section: that part is dropped, the code's section 2 is kept.
    chatty = model_reply("Bravo Base").replace("## 9.", "## 2. Serve\n\nInvented 99.9%.\n\n## 9.")
    report = assemble_report(sections, chatty)
    assert "Invented 99.9%" not in report and sections[2] in report

    # A model that forgets the Summary: the report says so instead of hiding it.
    forgetful = "## 9. Tactical takeaways for Bravo Base\n\n- A takeaway."
    result = check_report(assemble_report(sections, forgetful), data)
    assert "Missing section: Summary." in result["problems"]
