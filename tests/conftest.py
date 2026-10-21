"""A tiny fake dataset, built into a test database with the real build script.

The numbers are small and chosen by hand, so every expected percentage in test_stats.py
can be checked with a calculator. Players:
  ATP 1 Alpha Ace, 2 Bravo Base, 3 Charlie Clay, 4 Delta Drop
  WTA 10 Zoë Ząbek (accents, to test search), 11 Yara Young
"""

import csv

import pytest

import build_db

MATCH_COLUMNS = (
    "tourney_id,tourney_name,surface,draw_size,tourney_level,tourney_date,match_num,"
    "winner_id,winner_seed,winner_entry,winner_name,winner_hand,winner_ht,winner_ioc,winner_age,"
    "loser_id,loser_seed,loser_entry,loser_name,loser_hand,loser_ht,loser_ioc,loser_age,"
    "score,best_of,round,minutes,"
    "w_ace,w_df,w_svpt,w_1stIn,w_1stWon,w_2ndWon,w_SvGms,w_bpSaved,w_bpFaced,"
    "l_ace,l_df,l_svpt,l_1stIn,l_1stWon,l_2ndWon,l_SvGms,l_bpSaved,l_bpFaced,"
    "winner_rank,winner_rank_points,loser_rank,loser_rank_points"
).split(",")

NAMES = {1: "Alpha Ace", 2: "Bravo Base", 3: "Charlie Clay", 4: "Delta Drop", 10: "Zoë Ząbek", 11: "Yara Young"}


def serve(ace, df, svpt, first_in, first_won, second_won, sv_gms, bp_saved, bp_faced):
    return dict(ace=ace, df=df, svpt=svpt, **{"1stIn": first_in, "1stWon": first_won, "2ndWon": second_won},
                SvGms=sv_gms, bpSaved=bp_saved, bpFaced=bp_faced)


def match(tourney, surface, level, date, round_, winner, loser, score, w_serve=None, l_serve=None):
    row = {column: "" for column in MATCH_COLUMNS}
    row.update(tourney_id=f"2025-{tourney}", tourney_name=tourney, surface=surface, tourney_level=level,
               tourney_date=date, round=round_, best_of="3", score=score,
               winner_id=winner, winner_name=NAMES[winner], loser_id=loser, loser_name=NAMES[loser])
    for prefix, numbers in (("w", w_serve), ("l", l_serve)):
        for name, value in (numbers or {}).items():
            row[f"{prefix}_{name}"] = value
    return row


ATP_MATCHES = [
    # M1: Alpha beats Bravo on hard.
    match("Test Open", "Hard", "A", "20250303", "F", 1, 2, "6-4 6-4",
          serve(6, 3, 80, 50, 40, 15, 12, 2, 3), serve(4, 2, 70, 42, 30, 12, 11, 4, 7)),
    # M2: Bravo beats Alpha on clay.
    match("Clay Cup", "Clay", "A", "20250505", "F", 2, 1, "6-3 6-4",
          serve(5, 1, 65, 40, 30, 14, 10, 2, 4), serve(2, 4, 60, 36, 24, 10, 10, 3, 6)),
    # M3: Bravo retires: counts in the head-to-head, not in percentages.
    match("Hard Classic", "Hard", "A", "20250602", "SF", 1, 2, "6-3 2-1 RET",
          serve(1, 0, 30, 20, 15, 5, 4, 0, 0), serve(0, 1, 28, 15, 9, 6, 4, 1, 2)),
    # M4: walkover: listed, but not a win and no stats.
    match("Summer Open", "Hard", "A", "20250707", "QF", 1, 2, "W/O"),
    # M5: lowercase 'clay' must become 'Clay'; 0 serve points = no usable stats.
    match("Clay Cup", "clay", "A", "20250505", "R16", 3, 4, "6-2 6-2",
          serve(0, 0, 0, 0, 0, 0, 0, 0, 0), serve(1, 1, 40, 25, 15, 7, 8, 2, 5)),
]
WTA_MATCHES = [
    match("WTA Test", "Hard", "I", "20250303", "R32", 10, 11, "6-1 6-1"),
    # ITF event: must be excluded from the database.
    match("W50+H Somewhere", "Clay", "50+H", "20250414", "F", 11, 10, "6-0 6-0"),
]


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture(scope="session")
def fake_db(tmp_path_factory):
    """Path to a test database built from the fake files above."""
    raw = tmp_path_factory.mktemp("raw")
    write_csv(raw / "atp_matches_2025.csv", MATCH_COLUMNS, ATP_MATCHES)
    write_csv(raw / "wta_matches_2025.csv", MATCH_COLUMNS, WTA_MATCHES)
    player_columns = ["player_id", "name_first", "name_last", "hand", "dob", "ioc", "height", "wikidata_id"]
    for tour, ids in (("atp", [1, 2, 3, 4]), ("wta", [10, 11])):
        players = [{"player_id": i, "name_first": NAMES[i].split()[0], "name_last": NAMES[i].split()[1],
                    "hand": "R", "dob": "20000101", "ioc": "FRA", "height": "180", "wikidata_id": ""}
                   for i in ids]
        write_csv(raw / f"{tour}_players.csv", player_columns, players)
    write_csv(raw / "atp_rankings_current.csv", ["ranking_date", "rank", "player", "points"],
              [{"ranking_date": "20250609", "rank": 1, "player": 1, "points": 5000}])
    write_csv(raw / "wta_rankings_current.csv", ["ranking_date", "rank", "player", "points"],
              [{"ranking_date": "20250609", "rank": 5, "player": 10, "points": 3000}])

    db_path = tmp_path_factory.mktemp("db") / "test.db"
    build_db.build(raw_dir=raw, db_path=db_path, years=[2025])
    return db_path
