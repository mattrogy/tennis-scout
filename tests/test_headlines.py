"""Tests for model headlines: the checks, the plain replacements, and sections 1 and 9 (on the fake dataset)."""

import json

import pytest

from tennis_scout.facts import build_facts
from tennis_scout.headlines import (RESPONSE_FORMAT, WEBSITE_RULES, build_messages, direction_problem,
                                    headline_problem, write_sections)
from tennis_scout.report import gather_report_data

ALPHA, BRAVO = "atp-1", "atp-2"


@pytest.fixture
def report(fake_db):
    data = gather_report_data(ALPHA, coach=BRAVO, db_path=fake_db)
    return data, build_facts(data)


def reply(summary, takeaways):
    return json.dumps({"summary": summary, "takeaways": takeaways})


def item(headline, *facts):
    return {"headline": headline, "facts": list(facts)}


GOOD_SUMMARY = [item("How Alpha Ace's serve looks on hard courts", "F2"), item("A close head-to-head", "F17"),
                item("Recent form", "F21")]
GOOD_TAKEAWAYS = [item("Bravo's return will be tested", "F3"), item("Expect tight sets", "F18"),
                  item("Plan for Alpha's first serve", "F5")]


def test_facts_are_numbered_and_carry_only_tool_numbers(report):
    data, facts = report
    assert [fact["id"] for fact in facts] == [f"F{n}" for n in range(1, len(facts) + 1)]
    assert facts[0]["text"].startswith("Period covered:")
    assert "Alpha Ace's 1st serve in (all surfaces, 2 matches): 61.4%" in facts[2]["text"]
    assert all(not any(ch.isdigit() for ch in fact["topic"]) for fact in facts)  # plain headlines: no numbers
    # Every stat fact says whose stat it is and how it is labelled (2 matches here: not judged).
    assert facts[2]["labels"] == [{"player": "scouted", "label": "not judged"}]
    assert facts[1]["labels"] == []  # a count of labels is not itself a label


def test_the_model_sees_rules_and_facts_only(report):
    data, facts = report
    system, user = build_messages(data, facts)
    assert system == {"role": "system", "content": WEBSITE_RULES}
    assert "NO numbers" in WEBSITE_RULES and "week of" in WEBSITE_RULES
    assert user["content"].startswith("The coach's player is Bravo Base. The player being scouted is Alpha Ace.")
    for fact in facts:
        assert f"{fact['id']}: {fact['text']}" in user["content"]
    assert RESPONSE_FORMAT["json_schema"]["schema"]["required"] == ["summary", "takeaways"]


def test_good_headlines_are_kept_and_facts_copied_word_for_word(report):
    data, facts = report
    sections, log = write_sections(data, facts, reply(GOOD_SUMMARY, GOOD_TAKEAWAYS))
    assert log == []
    assert sections[1].startswith("## 1. Summary")
    assert "- **How Alpha Ace's serve looks on hard courts**\n  - " + facts[1]["text"] in sections[1]
    assert sections[9].startswith("## 9. Tactical takeaways for Bravo Base")
    assert "  - " + facts[17]["text"] in sections[9]  # F18


@pytest.mark.parametrize("headline, facts, reason", [
    ("Alcaraz wins 3 tie-breaks", ["F2"], "headline contains a digit"),
    ("Alpha Ace wins every tie-break", ["F2"], "sweeping word 'every'"),
    ("Alpha never loses on hard", ["F2"], "sweeping word 'never'"),
    ("An elite server", ["F2"], "stretching word 'elite'"),
    ("Hit deep returns to Alpha", ["F2"], "shot word 'deep'"),
    ("Alpha Ace is like Rafael Nadal", ["F2"], "name or capitalised word 'Rafael' is not one of the two players"),
    ("Alpha Ace serves well", ["F999"], "unknown fact IDs ['F999']"),
    ("Alpha Ace serves well", [], "must cite 1 to 4 facts"),
    ("Alpha Ace serves well", ["F2", "F3", "F4", "F5", "F6"], "must cite 1 to 4 facts"),
    ("", ["F2"], "empty headline"),
])
def test_each_rule_rejects_a_headline(report, headline, facts, reason):
    data, fact_list = report
    assert headline_problem(item(headline, *facts), data, {f["id"]: f for f in fact_list}) == reason


def test_the_two_players_and_surfaces_are_allowed(report):
    data, facts = report
    ids = {fact["id"]: fact for fact in facts}
    for headline in ("Bravo's serve against Alpha Ace's return", "On Clay, Alpha holds serve", "Expect Bravo Base to",
                     "Alpha Ace's numbers across all surfaces", "The all-surface numbers of Bravo"):
        assert headline_problem(item(headline, "F2"), data, ids) is None


def test_a_rejected_headline_is_replaced_by_a_plain_one_and_logged(report):
    data, facts = report
    bad = [item("Alpha wins 61.4% of first serves", "F3")] + GOOD_SUMMARY[1:]
    sections, log = write_sections(data, facts, reply(bad, GOOD_TAKEAWAYS))
    # The cited fact is kept, under the fact's plain topic instead of the model's headline.
    assert f"- **{facts[2]['topic']}**\n  - {facts[2]['text']}" in sections[1]
    assert "61.4% of first serves" not in sections[1]
    assert log == [{"section": "summary", "action": "replaced", "headline": "Alpha wins 61.4% of first serves",
                    "reason": "headline contains a digit"}]


def test_broken_or_short_replies_are_filled_with_code_headlines(report):
    data, facts = report
    sections, log = write_sections(data, facts, "Sorry, here is a poem instead.")
    assert log[0]["reason"] == "the reply is not valid JSON"
    assert sections[1].count("\n- **") == 3 and sections[9].count("\n- **") >= 3  # still a full report

    _, log = write_sections(data, facts, reply(GOOD_SUMMARY, GOOD_TAKEAWAYS[:1]))
    assert [entry["action"] for entry in log] == ["filled", "filled"]  # two takeaways added by code

    fenced = "```json\n" + reply(GOOD_SUMMARY, GOOD_TAKEAWAYS) + "\n```"
    assert write_sections(data, facts, fenced)[1] == []


# ---------------------------------------------------------------- direction rules (hand-made facts with labels)


def labelled(*labels):
    return {"labels": [{"player": player, "label": label} for player, label in labels]}


SCOUTED_WEAKNESS, SCOUTED_STRENGTH = labelled(("scouted", "weakness")), labelled(("scouted", "strength"))
SCOUTED_AVERAGE, NO_LABEL = labelled(("scouted", "average")), labelled()
COACH_STRENGTH, COACH_WEAKNESS = labelled(("coach", "strength")), labelled(("coach", "weakness"))


@pytest.mark.parametrize("headline, cited, ok", [
    # target / attack / exploit / go after: at least one weakness of the scouted player (average is not enough)
    ("Target Alpha's second serve", [SCOUTED_WEAKNESS], True),
    ("Target Alpha's second serve", [SCOUTED_AVERAGE], False),
    ("Attack the second serve", [SCOUTED_STRENGTH], False),
    ("Go after the second serve", [SCOUTED_WEAKNESS, SCOUTED_AVERAGE], True),
    ("Exploit the double faults", [COACH_WEAKNESS], False),  # the coach's own weakness is not a target
    # be ready for / prepare for / beware / respect: at least one strength of the scouted player
    ("Prepare for Alpha's return", [SCOUTED_STRENGTH], True),
    ("Be ready for Alpha's return", [SCOUTED_WEAKNESS], False),
    ("Respect Alpha in close sets", [SCOUTED_AVERAGE], False),
    ("Beware of Alpha's serve", [COACH_STRENGTH], False),
    # use / lean on / rely on: at least one strength of the coach's player
    ("Use Bravo's first serve", [COACH_STRENGTH], True),
    ("Lean on the first serve", [SCOUTED_STRENGTH], False),  # the scouted player's strength is not Bravo's
    ("Rely on the second serve", [COACH_WEAKNESS], False),
    # praising words: only strengths; negative words: only weaknesses
    ("Alpha returns well", [SCOUTED_STRENGTH, COACH_STRENGTH], True),
    ("A strong returner in close sets", [SCOUTED_STRENGTH, SCOUTED_AVERAGE], False),
    ("Alpha excels in tight moments", [SCOUTED_AVERAGE], False),
    ("A weapon on second serve", [NO_LABEL], False),  # praise needs at least one labelled fact
    ("Alpha struggles on second serve", [SCOUTED_WEAKNESS], True),
    ("Alpha struggles on second serve", [SCOUTED_AVERAGE], False),
    ("A low first serve percentage", [SCOUTED_STRENGTH], False),
    # neutral wording has no direction to check
    ("Expect tight sets against Alpha", [SCOUTED_AVERAGE], True),
])
def test_direction_must_match_the_cited_labels(headline, cited, ok):
    assert (direction_problem(headline, cited) is None) == ok


def test_a_misread_headline_is_replaced(report):
    data, facts = report
    # F3 is not judged (2 matches): praising it, or calling it a target, is a misread and gets replaced.
    misread = [item("Alpha's first serve is a weapon", "F3")] + GOOD_SUMMARY[1:]
    sections, log = write_sections(data, facts, reply(misread, GOOD_TAKEAWAYS))
    assert log[0]["action"] == "replaced" and "needs every labelled fact" in log[0]["reason"]
    assert "weapon" not in sections[1]
