"""Tests for the stats module.

Part 1 uses the tiny fake dataset from conftest.py: every expected number is calculated by hand.
Part 2 checks known real results in the full database (skipped if it has not been built yet).
"""

import csv
import sqlite3

import pytest

import build_db
from tennis_scout import stats
from tennis_scout.db import DB_PATH, PROJECT_ROOT

ALPHA, BRAVO, CHARLIE = "atp-1", "atp-2", "atp-3"


# ---------------------------------------------------------------- Part 1: hand-computed (fake data)


def test_serve_stats_all_surfaces(fake_db):
    result = stats.serve_stats(ALPHA, db_path=fake_db)
    # Alpha played M1, M2, M3 (retired) and M4 (walkover): only M1 and M2 are used.
    assert result["matches_found"] == 4
    assert result["matches_used"] == 2
    assert result["matches_excluded"] == {"walkover": 1, "retired_or_ended_early": 1, "no_usable_stats": 0}
    # M1 + M2: serve points 80+60=140, 1st in 50+36=86, 1st won 40+24=64, 2nd won 15+10=25,
    # aces 6+2=8, double faults 3+4=7, second serves 140-86=54.
    assert result["serve"] == {
        "first_serve_in_pct": 61.4,           # 86 / 140
        "second_serve_in_pct": 87.0,          # (54 - 7) / 54
        "first_serve_points_won_pct": 74.4,   # 64 / 86
        "second_serve_points_won_pct": 46.3,  # 25 / 54
        "aces_per_match": 4.0,                # 8 / 2
        "double_faults_per_match": 3.5,       # 7 / 2
        "break_points_saved_pct": 55.6,       # saved 2+3=5 of faced 3+6=9
    }


def test_serve_stats_surface_filter(fake_db):
    hard = stats.serve_stats(ALPHA, surface="hard", db_path=fake_db)
    # Hard: M1 (used), M3 (retired), M4 (walkover). Only M1 counts.
    assert (hard["matches_found"], hard["matches_used"]) == (3, 1)
    assert hard["serve"]["first_serve_in_pct"] == 62.5           # 50 / 80
    assert hard["serve"]["second_serve_in_pct"] == 90.0          # (30 - 3) / 30
    assert hard["serve"]["first_serve_points_won_pct"] == 80.0   # 40 / 50
    assert hard["serve"]["second_serve_points_won_pct"] == 50.0  # 15 / 30

    clay = stats.serve_stats(ALPHA, surface="Clay", db_path=fake_db)
    # Clay: M2 only. 36/60 in, (24-4)/24 second in, 24/36 won, 10/24 won.
    assert clay["serve"]["first_serve_in_pct"] == 60.0
    assert clay["serve"]["second_serve_in_pct"] == 83.3
    assert clay["serve"]["first_serve_points_won_pct"] == 66.7
    assert clay["serve"]["second_serve_points_won_pct"] == 41.7


def test_serve_stats_date_filter(fake_db):
    result = stats.serve_stats(ALPHA, date_from="2025-01-01", date_to="2025-04-30", db_path=fake_db)
    assert result["matches_found"] == 1  # only M1 (2025-03-03)
    assert result["serve"]["first_serve_in_pct"] == 62.5
    assert result["filters"] == {"surface": None, "date_from": "2025-01-01", "date_to": "2025-04-30"}


def test_lowercase_surface_and_invalid_stats(fake_db):
    # M5 was written as 'clay' in the file, and Charlie's serve points are 0.
    result = stats.serve_stats(CHARLIE, surface="Clay", db_path=fake_db)
    assert result["matches_found"] == 1
    assert result["matches_used"] == 0
    assert result["matches_excluded"]["no_usable_stats"] == 1
    assert result["serve"] is None


def test_head_to_head(fake_db):
    result = stats.head_to_head(ALPHA, BRAVO, db_path=fake_db)
    # Alpha won M1 and M3 (retirement counts); Bravo won M2; the M4 walkover is listed but not counted.
    assert result["wins"] == {"Alpha Ace": 2, "Bravo Base": 1}
    assert result["matches_used"] == 3
    assert result["matches_listed"] == 4
    assert [m["tournament"] for m in result["matches"]] == ["Test Open", "Clay Cup", "Hard Classic", "Summer Open"]
    assert result["matches"][3]["finish"] == "walkover"
    assert result["matches"][0]["date"] == "week of 3 March 2025"

    clay = stats.head_to_head(ALPHA, BRAVO, surface="Clay", db_path=fake_db)
    assert clay["wins"] == {"Alpha Ace": 0, "Bravo Base": 1}


def test_head_to_head_tiebreaks_are_decoded(fake_db):
    result = stats.head_to_head(ALPHA, BRAVO, db_path=fake_db)
    # M1 '7-6(5) 4-6 6-3' (Alpha won): Alpha wins the tie-break.
    # M2 '6-7(3) 7-6(5) 6-4' (Bravo won, so written from Bravo's side): Alpha wins TB 1, Bravo wins TB 2.
    assert result["matches"][1]["tiebreaks_won"] == {"Alpha Ace": 1, "Bravo Base": 1}
    assert result["tiebreak_summary"] == {"completed_matches": 2, "matches_with_a_tiebreak": 2,
                                          "tiebreaks_won": {"Alpha Ace": 2, "Bravo Base": 1}}
    # Both completed matches went to a 3rd set: Alpha won M1's, Bravo won M2's.
    assert result["deciding_set_summary"]["deciding_sets_won"] == {"Alpha Ace": 1, "Bravo Base": 1}
    assert [m["went_to_deciding_set"] for m in result["matches"]] == [True, True, False, False]


def test_find_player(fake_db):
    found = stats.find_player("alpha", db_path=fake_db)["candidates"]
    assert [p["player_key"] for p in found] == [ALPHA]
    assert found[0]["current_rank"] == 1
    assert found[0]["rank_as_of"] == "9 June 2025"

    # Accents and capitals are ignored, in both the query and the stored name.
    assert stats.find_player("ZĄBEK", db_path=fake_db)["candidates"][0]["player_key"] == "wta-10"
    assert stats.find_player("alpha", tour="wta", db_path=fake_db)["candidates"] == []


def test_every_answer_carries_source_and_freshness(fake_db):
    for result in (stats.find_player("bravo", db_path=fake_db),
                   stats.serve_stats(BRAVO, db_path=fake_db),
                   stats.return_stats(BRAVO, db_path=fake_db),
                   stats.pressure_stats(BRAVO, db_path=fake_db),
                   stats.recent_form(BRAVO, db_path=fake_db),
                   stats.head_to_head(ALPHA, BRAVO, db_path=fake_db)):
        assert "Jeff Sackmann" in result["source"]
        assert "CC BY-NC-SA 4.0" in result["source"]
        assert result["data_note"].startswith("Data through July 2025")


def test_itf_matches_are_excluded(fake_db):
    db = sqlite3.connect(fake_db)
    assert db.execute("SELECT COUNT(*) FROM matches WHERE tour = 'wta'").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM matches WHERE tourney_level = '50+H'").fetchone()[0] == 0
    db.close()


@pytest.mark.parametrize("bad_call, message", [
    (dict(player="atp-999"), "Use find_player first"),
    (dict(player=ALPHA, surface="Carpet"), "Surface must be one of"),
    (dict(player=ALPHA, date_from="03/03/2025"), "YYYY-MM-DD"),
    (dict(player=ALPHA, date_from="2025-06-01", date_to="2025-01-01"), "before date_to"),
])
def test_clear_errors(fake_db, bad_call, message):
    with pytest.raises(stats.StatsError, match=message):
        stats.serve_stats(db_path=fake_db, **bad_call)


def test_level_rules():
    assert build_db.level_name("wta", "W", "Eastbourne") == "WTA 250/500"  # 2021 tour event: kept
    assert build_db.level_name("wta", "W", "WTA Finals") == "WTA Finals"
    assert build_db.level_name("wta", "W", "Buenos Aires 125") == build_db.EXCLUDE
    assert build_db.level_name("wta", "35+H", "W35+H Tauste") == build_db.EXCLUDE
    assert build_db.level_name("atp", "F", "Next Gen Finals") == "Next Gen Finals"
    with pytest.raises(ValueError, match="Unknown tourney_level"):
        build_db.level_name("atp", "C", "Some Challenger")


def test_finish_types():
    assert build_db.finish_type("6-3 2-1 RET") == "retired"
    assert build_db.finish_type("W/O") == "walkover"
    assert build_db.finish_type("Walkover") == "walkover"
    assert build_db.finish_type("6-4 3-2 DEF") == "defaulted"
    assert build_db.finish_type("7-6(5) 6-3") == "completed"


@pytest.mark.parametrize("score, expected", [
    # (tie-breaks won by the winner, tie-breaks won by the loser, sets played)
    ("7-6(5) 4-6 6-3", (1, 0, 3)),
    ("6-7(4) 7-6(3) 7-6(2)", (2, 1, 3)),
    ("7-6(5) 1-6 7-6(4) 4-6 13-12(3)", (3, 0, 5)),  # Wimbledon 2019: tie-break at 12-12
    ("4-6 6-3 [10-7]", (0, 0, 3)),                  # match tie-break: a set, not a tie-break
    ("6-3 2-1 RET", (0, 0, 2)),
    ("W/O", (0, 0, 0)),
])
def test_score_summary(score, expected):
    assert build_db.score_summary(score) == expected


def test_team_events_are_labelled():
    assert build_db.level_name("atp", "A", "Laver Cup") == "Team event"
    assert build_db.level_name("wta", "I", "United Cup") == "Team event"


def test_return_stats(fake_db):
    result = stats.return_stats(ALPHA, db_path=fake_db)
    assert (result["matches_found"], result["matches_used"]) == (4, 2)
    # Bravo's serve in M1 + M2: 1st in 42+40=82, 1st won 30+30=60, serve points 70+65=135,
    # 2nd serves 135-82=53, 2nd won 12+14=26, break points faced 7+4=11, saved 4+2=6.
    assert result["return"] == {
        "return_points_won_vs_first_serve_pct": 26.8,   # (82 - 60) / 82
        "return_points_won_vs_second_serve_pct": 50.9,  # (53 - 26) / 53
        "break_points_converted_pct": 45.5,             # (11 - 6) / 11
    }
    hard = stats.return_stats(ALPHA, surface="Hard", db_path=fake_db)
    # M1 only: (42-30)/42, (28-12)/28, (7-4)/7.
    assert hard["return"] == {
        "return_points_won_vs_first_serve_pct": 28.6,
        "return_points_won_vs_second_serve_pct": 57.1,
        "break_points_converted_pct": 42.9,
    }


def test_pressure_stats(fake_db):
    result = stats.pressure_stats(ALPHA, db_path=fake_db)
    # Used: M1 and M2. Skipped: M3 (retirement) and M4 (walkover).
    assert result["matches_used"] == 2
    assert result["matches_skipped"] == {"walkover": 1, "retired_or_ended_early": 1, "next_gen_finals_rules": 0}
    # Tie-breaks: won in M1, won and lost in M2. Deciding sets: won M1, lost M2.
    assert result["tie_breaks"] == {"played": 3, "won": 2, "lost": 1, "won_pct": 66.7}
    assert result["deciding_sets"] == {"played": 2, "won": 1, "lost": 1, "won_pct": 50.0}

    hard = stats.pressure_stats(ALPHA, surface="Hard", db_path=fake_db)
    assert hard["tie_breaks"]["played"] == 1 and hard["deciding_sets"]["won"] == 1


def test_pressure_match_tiebreak_and_next_gen(fake_db):
    result = stats.pressure_stats(CHARLIE, db_path=fake_db)
    # Charlie: M5 (no serve stats, but the score is enough), M6 ([10-7]) used; M7 (Next Gen Finals) skipped.
    assert result["matches_used"] == 2
    assert result["matches_skipped"]["next_gen_finals_rules"] == 1
    assert result["tie_breaks"]["played"] == 0  # the [10-7] is not a tie-break; M7's tie-break is skipped
    assert result["deciding_sets"] == {"played": 1, "won": 1, "lost": 0, "won_pct": 100.0}


def test_recent_form(fake_db):
    result = stats.recent_form(ALPHA, n=10, db_path=fake_db)
    # Newest first: M4 (walkover), M3 (Bravo retired), M2 (loss), M1 (win).
    assert [m["tournament"] for m in result["matches"]] == ["Summer Open", "Hard Classic", "Clay Cup", "Test Open"]
    assert [m["note"] for m in result["matches"]] == ["w/o", "ret.", None, None]
    assert result["summary"]["wins"] == 2 and result["summary"]["losses"] == 1
    assert result["summary"]["walkovers_listed_not_counted"] == 1
    assert result["current_ranking"] == {"rank": 1, "points": 5000, "as_of": "9 June 2025"}
    clay_cup = result["matches"][2]  # M2, from Alpha's side: won 1 tie-break, lost 1, went to a 3rd set
    assert (clay_cup["tiebreaks_won"], clay_cup["tiebreaks_lost"], clay_cup["went_to_deciding_set"]) == (1, 1, True)

    bravo = stats.recent_form(BRAVO, n=2, db_path=fake_db)
    assert len(bravo["matches"]) == 2
    assert bravo["matches"][1]["note"] == "retired"  # Bravo retired in M3
    assert bravo["summary"]["retired_text"] == "Retired in 1 of the last 2 matches."
    assert bravo["current_ranking"]["rank"] == "unranked"


@pytest.mark.parametrize("n", [0, 51, "ten"])
def test_recent_form_rejects_bad_n(fake_db, n):
    with pytest.raises(stats.StatsError, match="between 1 and 50"):
        stats.recent_form(ALPHA, n=n, db_path=fake_db)


# ---------------------------------------------------------------- Part 1b: comparison with the tour (fake data)


@pytest.fixture
def small_thresholds(monkeypatch):
    """The fake data has 2 matches per player and 2 players with stats: lower the thresholds to 1."""
    monkeypatch.setattr(stats, "MIN_MATCHES", 1)
    monkeypatch.setattr(stats, "MIN_PEERS", 1)


def test_compared_to_tour(fake_db, small_thresholds):
    alpha = stats.serve_stats(ALPHA, db_path=fake_db)["compared_to_tour"]
    # Only Alpha and Bravo have usable stats. Bravo's 1st serve in: 82/135 = 60.7%, below Alpha's 61.4%.
    # Tour average = all used ATP serve points: (86 + 82) / (140 + 135) = 61.1%.
    assert alpha["first_serve_in_pct"] == {"tour_average": 61.1, "peers": 1, "percentile": 100, "label": "strength"}
    # Double faults per match, lower is better: Alpha 3.5 vs Bravo 1.5, so Alpha is worse.
    assert alpha["double_faults_per_match"]["percentile"] == 0
    assert alpha["double_faults_per_match"]["label"] == "weakness"

    bravo = stats.serve_stats(BRAVO, db_path=fake_db)["compared_to_tour"]
    assert bravo["first_serve_in_pct"]["label"] == "weakness"


def test_pressure_comparison_has_no_tour_average(fake_db, small_thresholds):
    result = stats.pressure_stats(ALPHA, db_path=fake_db)["compared_to_tour"]["tie_breaks_won_pct"]
    # Alpha won 2 of 3 tie-breaks (66.7%), Bravo 1 of 3 (33.3%). Charlie and Delta have no tie-breaks to compare.
    assert result == {"peers": 1, "percentile": 100, "label": "strength"}


def test_not_enough_data_and_not_enough_peers(fake_db, monkeypatch):
    # Real thresholds: Alpha has only 2 matches (< 10).
    assert stats.serve_stats(ALPHA, db_path=fake_db)["compared_to_tour"]["first_serve_in_pct"]["label"] == "not enough data"
    # Enough matches, but 1 peer is far below the minimum of 30.
    monkeypatch.setattr(stats, "MIN_MATCHES", 1)
    entry = stats.serve_stats(ALPHA, db_path=fake_db)["compared_to_tour"]["first_serve_in_pct"]
    assert (entry["label"], entry["peers"], entry["percentile"]) == ("not enough peers", 1, None)


def test_matchup(fake_db, small_thresholds):
    result = stats.matchup(ALPHA, BRAVO, db_path=fake_db)
    first_serve = result["when Alpha Ace serves"][0]
    assert first_serve["server"]["value"] == 74.4    # Alpha's 1st serve points won: 64 / 86
    assert first_serve["returner"]["value"] == 25.6  # Bravo's return vs 1st serve: (86 - 64) / 86
    # They only played each other, so every 1st-serve point Alpha did not win, Bravo won.
    assert first_serve["server"]["value"] + first_serve["returner"]["value"] == 100.0
    break_points = result["when Bravo Base serves"][2]
    assert break_points["about"] == "break points"
    assert break_points["returner"]["value"] == 45.5  # Alpha converted 5 of 11 (same as return_stats)


def test_default_report_period(fake_db):
    # Fake data runs through 2025-07-07: the 24 months are August 2023 to July 2025.
    assert stats.default_report_period(db_path=fake_db) == {
        "date_from": "2023-08-01", "date_to": "2025-07-07", "label": "August 2023 – July 2025",
    }


# ---------------------------------------------------------------- Part 2: known real results

real = pytest.mark.skipif(not DB_PATH.exists(), reason="real database not built (run scripts/build_db.py)")
SINNER, ALCARAZ = "atp-206173", "atp-207989"


@real
def test_real_find_player():
    assert stats.find_player("alcaraz")["candidates"][0]["name"] == "Carlos Alcaraz"
    assert stats.find_player("Świątek")["candidates"][0]["name"] == "Iga Swiatek"


@real
def test_real_head_to_head_contains_2025_slam_finals():
    finals = [(m["tournament"], m["date"], m["winner"])
              for m in stats.head_to_head(SINNER, ALCARAZ)["matches"] if m["round"] == "F"]
    assert ("Roland Garros", "week of 26 May 2025", "Carlos Alcaraz") in finals
    assert ("Wimbledon", "week of 30 June 2025", "Jannik Sinner") in finals


@real
def test_real_serve_stats_match_raw_csv():
    """Alcaraz at Roland Garros 2025, summed straight from the raw CSV (independent of the SQL)."""
    totals = {"svpt": 0, "1stIn": 0, "ace": 0}
    with open(PROJECT_ROOT / "data" / "raw" / "atp_matches_2025.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["tourney_name"] != "Roland Garros" or "RET" in row["score"] or "W/O" in row["score"]:
                continue
            for side, name in (("w", row["winner_name"]), ("l", row["loser_name"])):
                if name == "Carlos Alcaraz":
                    for key in totals:
                        totals[key] += int(row[f"{side}_{key}"])

    result = stats.serve_stats(ALCARAZ, date_from="2025-05-26", date_to="2025-05-26")
    # He won the title (7 matches), but Musetti retired in the semi-final, so 6 are used.
    assert result["matches_found"] == 7
    assert result["matches_used"] == 6
    assert result["matches_excluded"]["retired_or_ended_early"] == 1
    assert result["totals"]["serve_points"] == totals["svpt"]
    assert result["totals"]["first_serves_in"] == totals["1stIn"]
    assert result["totals"]["aces"] == totals["ace"]


@real
def test_real_scope_and_freshness():
    db = sqlite3.connect(DB_PATH)
    assert db.execute("SELECT COUNT(*) FROM matches WHERE tourney_level IN ('35+H', '50+H')").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM matches WHERE tourney_name LIKE '%125%'").fetchone()[0] == 0
    # The 2021 'W' events are real tour events and must be kept.
    assert db.execute("SELECT COUNT(*) FROM matches WHERE tour = 'wta' AND tourney_name = 'Eastbourne' "
                      "AND tourney_date LIKE '2021%'").fetchone()[0] > 0
    db.close()
    result = stats.find_player("sinner")
    assert result["data_note"].startswith("Data through May 2026")
    assert result["candidates"][0]["rank_as_of"] == "8 June 2026"


@real
def test_real_head_to_head_tiebreaks_on_clay():
    """The errors seen in early AI reports: who won the Umag 2022 tie-break, and how many clay meetings had one."""
    result = stats.head_to_head(ALCARAZ, SINNER, surface="Clay")
    umag = next(m for m in result["matches"] if m["tournament"] == "Umag")
    # '6-7(5) 6-1 6-1' is written from Sinner's side (he won the match): Alcaraz won that tie-break.
    assert umag["tiebreaks_won"] == {"Carlos Alcaraz": 1, "Jannik Sinner": 0}
    assert result["tiebreak_summary"]["matches_with_a_tiebreak"] == 4  # Umag, Rome 2025, Roland Garros 2025, Monte Carlo
    assert result["tiebreak_summary"]["tiebreaks_won"] == {"Carlos Alcaraz": 4, "Jannik Sinner": 2}


@real
def test_real_recent_form_sinner():
    result = stats.recent_form(SINNER, n=3)
    latest, before = result["matches"][0], result["matches"][1]
    # Same tournament week: the R64 must come before the R128 (round order, newest first).
    assert (latest["tournament"], latest["round"], latest["result"]) == ("Roland Garros", "R64", "L")
    assert latest["opponent"] == "Juan Manuel Cerundolo"
    assert before["round"] == "R128"
    assert result["current_ranking"]["rank"] == 1
    assert result["current_ranking"]["as_of"] == "8 June 2026"


@real
def test_real_pressure_alcaraz_roland_garros_2025():
    result = stats.pressure_stats(ALCARAZ, date_from="2025-05-26", date_to="2025-05-26")
    # Tie-breaks: 7-6(8) vs Shelton, then lost 1 and won 2 in the final. The Musetti semi-final (retired) is skipped.
    assert result["matches_skipped"]["retired_or_ended_early"] == 1
    assert result["tie_breaks"] == {"played": 4, "won": 3, "lost": 1, "won_pct": 75.0}
    assert result["deciding_sets"] == {"played": 1, "won": 1, "lost": 0, "won_pct": 100.0}  # the 5-set final


@real
def test_real_return_stats_match_raw_csv():
    """Alcaraz's return at Roland Garros 2025, summed straight from the raw CSV (opponents' serve numbers)."""
    first_in = first_won = bp_faced = 0
    with open(PROJECT_ROOT / "data" / "raw" / "atp_matches_2025.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["tourney_name"] != "Roland Garros" or "RET" in row["score"] or "W/O" in row["score"]:
                continue
            for name, opponent_side in ((row["winner_name"], "l"), (row["loser_name"], "w")):
                if name == "Carlos Alcaraz":
                    first_in += int(row[f"{opponent_side}_1stIn"])
                    first_won += int(row[f"{opponent_side}_1stWon"])
                    bp_faced += int(row[f"{opponent_side}_bpFaced"])

    result = stats.return_stats(ALCARAZ, date_from="2025-05-26", date_to="2025-05-26")
    assert result["totals"]["first_serve_return_points"] == first_in
    assert result["totals"]["first_serve_return_points_won"] == first_in - first_won
    assert result["totals"]["break_points"] == bp_faced


@real
def test_real_default_report_period():
    assert stats.default_report_period() == {
        "date_from": "2024-06-01", "date_to": "2026-05-25", "label": "June 2024 – May 2026",
    }


@real
def test_real_serve_plus_return_equals_100():
    """Every serve point is someone's return point, so the tour averages must add up to 100%."""
    serve = stats.serve_stats(ALCARAZ, surface="Clay")["compared_to_tour"]
    ret = stats.return_stats(ALCARAZ, surface="Clay")["compared_to_tour"]
    total = (serve["first_serve_points_won_pct"]["tour_average"]
             + ret["return_points_won_vs_first_serve_pct"]["tour_average"])
    assert abs(total - 100) <= 0.1  # each average is rounded to 1 decimal


@real
def test_real_alcaraz_clay_labels():
    serve = stats.serve_stats(ALCARAZ, surface="Clay")["compared_to_tour"]
    ret = stats.return_stats(ALCARAZ, surface="Clay")["compared_to_tour"]
    assert ret["return_points_won_vs_first_serve_pct"]["label"] == "strength"
    assert serve["first_serve_points_won_pct"]["label"] == "average"
    assert serve["aces_per_match"]["label"] == "weakness"
    assert serve["aces_per_match"]["peers"] >= stats.MIN_PEERS


@real
def test_real_matchup_matches_the_separate_tools():
    period = stats.default_report_period()
    filters = {"surface": "Clay", "date_from": period["date_from"], "date_to": period["date_to"]}
    result = stats.matchup(SINNER, ALCARAZ, **filters)
    pair = result["when Jannik Sinner serves"][0]
    assert pair["server"]["value"] == stats.serve_stats(SINNER, **filters)["serve"]["first_serve_points_won_pct"]
    assert pair["returner"]["value"] == stats.return_stats(ALCARAZ, **filters)["return"][
        "return_points_won_vs_first_serve_pct"]
