"""Build data/tennis.db from the raw CSV files in data/raw/.

Run scripts/download_data.py first. This script rebuilds the database from scratch every time:
    uv run python scripts/build_db.py

What it does, in order:
  1. reads the match files, cleans them (surface, level, how the match finished) and keeps tour-level only
  2. loads the players who appear in those matches
  3. loads the current rankings
  4. creates a "player_matches" view: one row per player per match, seen from that player's side
  5. stores where the data came from and how fresh it is in a "meta" table
"""

import csv
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from tennis_scout.db import DB_PATH, normalize_name

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
TOURS = ["atp", "wta"]
FIRST_YEAR = 2015
LAST_YEAR = 2026

SOURCE_REPO = "Aneeshers/tennis-sackmann-archive"
SOURCE_COMMIT = "83733587353df8a41f2fd4f516147d5aa83f5a8d"

# Column types in the match files. Every column not listed here is a whole number.
TEXT_COLUMNS = {
    "tourney_id", "tourney_name", "surface", "tourney_level", "tourney_date", "score", "round",
    "winner_seed", "winner_entry", "winner_name", "winner_hand", "winner_ioc",
    "loser_seed", "loser_entry", "loser_name", "loser_hand", "loser_ioc",
}
DECIMAL_COLUMNS = {"winner_age", "loser_age"}

# The serve numbers we need for every percentage stat (w_ = winner, l_ = loser).
SERVE_COLUMNS = ["ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced"]

ATP_LEVELS = {
    "G": "Grand Slam",
    "M": "Masters 1000",
    "A": "ATP 500/250",
    "F": "Tour Finals",
    "D": "Davis Cup",
    "O": "Olympics",
}
WTA_LEVELS = {
    "G": "Grand Slam",
    "PM": "WTA 1000 (Premier Mandatory before 2021)",
    "P": "WTA 500 (Premier before 2021)",
    "I": "WTA 250 (International before 2021)",
    "F": "WTA Finals",
    "D": "Billie Jean King Cup",
    "O": "Olympics",
}
SURFACES = {"hard": "Hard", "clay": "Clay", "grass": "Grass", "carpet": "Carpet"}

# Returned by level_name() for matches we do not load (out of scope).
EXCLUDE = "EXCLUDE"


def level_name(tour, code, tourney_name):
    """Turn Sackmann's level code into a readable name, or EXCLUDE for out-of-scope events."""
    if tour == "atp":
        if code == "F" and "next" in tourney_name.lower():
            return "Next Gen Finals"
        if code in ATP_LEVELS:
            return ATP_LEVELS[code]
    else:
        if code in ("35+H", "50+H"):
            return EXCLUDE  # ITF W35/W50 events: not tour-level
        if code == "W":
            # "W" means different things in different years, so the tournament name decides.
            if "finals" in tourney_name.lower():
                return "WTA Finals"
            if "125" in tourney_name:
                return EXCLUDE  # WTA 125 = the women's equivalent of ATP Challengers
            return "WTA 250/500"  # 2021 events such as Eastbourne or Strasbourg
        if code in WTA_LEVELS:
            return WTA_LEVELS[code]
    # Stop loudly rather than silently mislabel a match.
    raise ValueError(f"Unknown tourney_level {code!r} for {tour} tournament {tourney_name!r}")


def clean_surface(raw):
    """'clay' -> 'Clay'; blank -> None (unknown)."""
    return SURFACES.get(raw.strip().lower())


def finish_type(score):
    """How the match ended, read from the score text (e.g. '6-3 2-1 RET')."""
    words = score.upper().split()
    if "W/O" in words or "WALKOVER" in words:
        return "walkover"
    if "RET" in words:
        return "retired"
    if "DEF" in words or "DEF." in words:
        return "defaulted"
    if "ABD" in words:
        return "abandoned"
    return "completed"


def to_value(column, text):
    """Convert one CSV cell to the right Python type; empty cells become None (NULL in SQL)."""
    text = text.strip()
    if text == "":
        return None
    if column in TEXT_COLUMNS:
        return text
    if column in DECIMAL_COLUMNS:
        return float(text)
    return int(float(text))  # int(float()) also accepts values written like '185.0'


def serve_stats_ok(row, side):
    """True if one side's serve numbers are complete and physically possible."""
    values = {name: row[f"{side}_{name}"] for name in SERVE_COLUMNS}
    if any(value is None for value in values.values()):
        return False
    second_serves = values["svpt"] - values["1stIn"]
    return (
        values["svpt"] > 0
        and values["1stIn"] <= values["svpt"]
        and values["1stWon"] <= values["1stIn"]
        and values["2ndWon"] + values["df"] <= second_serves
        and values["bpSaved"] <= values["bpFaced"]
    )


def iso_date(yyyymmdd):
    """'20250526' -> '2025-05-26'."""
    text = str(yyyymmdd)
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def read_csv(path):
    """Read a CSV as a list of dicts. Files are UTF-8; Latin-1 is a fallback for odd files."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except UnicodeDecodeError:
        with open(path, encoding="latin-1", newline="") as f:
            return list(csv.DictReader(f))


def create_tables(db, match_columns):
    column_sql = []
    for column in match_columns:
        sql_type = "TEXT" if column in TEXT_COLUMNS else "REAL" if column in DECIMAL_COLUMNS else "INTEGER"
        column_sql.append(f'"{column}" {sql_type}')
    db.executescript(f"""
        CREATE TABLE matches (
            match_id INTEGER PRIMARY KEY,
            tour TEXT NOT NULL,
            level_name TEXT NOT NULL,
            finish TEXT NOT NULL,          -- completed / retired / defaulted / abandoned / walkover
            stats_ok INTEGER NOT NULL,     -- 1 if both players' serve numbers are complete and valid
            winner_key TEXT NOT NULL,      -- e.g. 'atp-206173'
            loser_key TEXT NOT NULL,
            {", ".join(column_sql)}
        );
        CREATE TABLE players (
            player_key TEXT PRIMARY KEY,
            tour TEXT NOT NULL,
            player_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_search TEXT NOT NULL,     -- lowercase, no accents, for searching
            hand TEXT,
            country TEXT,
            birth_date TEXT,
            height_cm INTEGER
        );
        CREATE TABLE rankings (
            tour TEXT NOT NULL,
            ranking_date TEXT NOT NULL,
            rank INTEGER NOT NULL,
            player_key TEXT NOT NULL,
            points INTEGER
        );
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)


def load_matches(db, raw_dir, years):
    """Load all match files. Returns the counters printed in the summary."""
    loaded = Counter()      # (tour, year) -> matches loaded
    excluded = Counter()    # reason -> matches skipped
    finishes = Counter()
    match_columns = None

    for tour in TOURS:
        for year in years:
            rows = read_csv(raw_dir / f"{tour}_matches_{year}.csv")
            if match_columns is None:
                match_columns = list(rows[0].keys())
                create_tables(db, match_columns)

            for raw in rows:
                level = level_name(tour, raw["tourney_level"], raw["tourney_name"])
                if level == EXCLUDE:
                    excluded[f"{tour} level {raw['tourney_level']} ({raw['tourney_name']})"] += 1
                    continue

                row = {column: to_value(column, raw[column]) for column in match_columns}
                row["surface"] = clean_surface(raw["surface"])
                row["tourney_date"] = iso_date(raw["tourney_date"])
                row["tour"] = tour
                row["level_name"] = level
                row["finish"] = finish_type(raw["score"])
                row["stats_ok"] = int(serve_stats_ok(row, "w") and serve_stats_ok(row, "l"))
                row["winner_key"] = f"{tour}-{row['winner_id']}"
                row["loser_key"] = f"{tour}-{row['loser_id']}"

                columns = ", ".join(f'"{c}"' for c in row)
                placeholders = ", ".join("?" for _ in row)
                db.execute(f"INSERT INTO matches ({columns}) VALUES ({placeholders})", list(row.values()))
                loaded[(tour, year)] += 1
                finishes[row["finish"]] += 1

    return loaded, excluded, finishes


def load_players(db, raw_dir):
    """Load only the players who appear in the loaded matches."""
    for tour in TOURS:
        players_file = {row["player_id"]: row for row in read_csv(raw_dir / f"{tour}_players.csv")}
        # The name used in the match files, as a fallback if the players file lacks one.
        seen = db.execute("""
            SELECT winner_id AS id, winner_name AS name FROM matches WHERE tour = ?
            UNION SELECT loser_id, loser_name FROM matches WHERE tour = ?
        """, (tour, tour)).fetchall()
        for player_id, match_name in seen:
            info = players_file.get(str(player_id), {})
            full_name = f"{info.get('name_first', '')} {info.get('name_last', '')}".strip() or match_name
            birth = info.get("dob", "").strip()
            height = info.get("height", "").strip()
            db.execute(
                "INSERT OR IGNORE INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"{tour}-{player_id}", tour, player_id, full_name, normalize_name(full_name),
                    info.get("hand") or None, info.get("ioc") or None,
                    iso_date(birth) if len(birth) == 8 else None,
                    int(float(height)) if height else None,
                ),
            )


def load_rankings(db, raw_dir):
    for tour in TOURS:
        for row in read_csv(raw_dir / f"{tour}_rankings_current.csv"):
            db.execute(
                "INSERT INTO rankings VALUES (?, ?, ?, ?, ?)",
                (tour, iso_date(row["ranking_date"]), int(row["rank"]), f"{tour}-{row['player']}",
                 int(float(row["points"])) if row["points"] else None),
            )


def create_view_and_indexes(db):
    # Each match appears twice: once from the winner's side (won = 1), once from the loser's (won = 0).
    # "player_*" columns are the player's own serve numbers, "opp_*" columns are the opponent's.
    sides = []
    for me, opp, won in (("w", "l", 1), ("l", "w", 0)):
        me_name, opp_name = ("winner", "loser") if me == "w" else ("loser", "winner")
        own = ", ".join(f'"{me}_{c}" AS "{c}"' for c in SERVE_COLUMNS)
        theirs = ", ".join(f'"{opp}_{c}" AS "opp_{c}"' for c in SERVE_COLUMNS)
        sides.append(f"""
            SELECT match_id, tour, tourney_date, tourney_name, level_name, surface, round, best_of,
                   score, finish, stats_ok, {won} AS won,
                   {me_name}_key AS player_key, {opp_name}_key AS opponent_key,
                   {me_name}_name AS player_name, {opp_name}_name AS opponent_name,
                   {me_name}_rank AS player_rank, {opp_name}_rank AS opponent_rank,
                   {own}, {theirs}
            FROM matches""")
    db.executescript(f"""
        CREATE VIEW player_matches AS {" UNION ALL ".join(sides)};
        CREATE INDEX idx_matches_winner ON matches (winner_key, tourney_date);
        CREATE INDEX idx_matches_loser ON matches (loser_key, tourney_date);
        CREATE INDEX idx_matches_surface ON matches (surface);
        CREATE INDEX idx_players_search ON players (name_search);
        CREATE INDEX idx_rankings_player ON rankings (player_key, ranking_date);
    """)


def save_meta(db):
    data_through = db.execute("SELECT MAX(tourney_date) FROM matches").fetchone()[0]
    rankings_as_of = db.execute("SELECT MAX(ranking_date) FROM rankings").fetchone()[0]
    meta = {
        "source_repo": SOURCE_REPO,
        "source_commit": SOURCE_COMMIT,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_through": data_through,      # latest tournament start date, e.g. 2026-05-25
        "rankings_as_of": rankings_as_of,  # latest ranking week, e.g. 2026-06-08
    }
    db.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
    return meta


def build(raw_dir=RAW_DIR, db_path=DB_PATH, years=range(FIRST_YEAR, LAST_YEAR + 1)):
    """Build the database. The arguments let the tests build a tiny database from fake files."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = db_path.with_suffix(".building")
    temp_path.unlink(missing_ok=True)

    db = sqlite3.connect(temp_path)
    loaded, excluded, finishes = load_matches(db, Path(raw_dir), years)
    load_players(db, Path(raw_dir))
    load_rankings(db, Path(raw_dir))
    create_view_and_indexes(db)
    meta = save_meta(db)
    db.commit()

    # Summary, so the numbers can be checked by eye.
    print("Matches loaded per year:")
    for tour in TOURS:
        counts = "  ".join(f"{year}: {loaded[(tour, year)]}" for year in years)
        print(f"  {tour.upper()}  {counts}")
    print(f"Total matches: {sum(loaded.values())}")
    print("How matches finished:", dict(finishes))
    stats_ok = db.execute("SELECT SUM(stats_ok), COUNT(*) FROM matches").fetchone()
    print(f"Matches with usable serve stats: {stats_ok[0]} of {stats_ok[1]}")
    no_surface = db.execute("SELECT COUNT(*) FROM matches WHERE surface IS NULL").fetchone()[0]
    print(f"Matches with unknown surface: {no_surface}")
    print("Excluded (out of scope):")
    for reason, count in sorted(excluded.items()):
        print(f"  {count:4d}  {reason}")
    print(f"Players: {db.execute('SELECT COUNT(*) FROM players').fetchone()[0]}")
    print(f"Data through {meta['data_through']}, rankings as of {meta['rankings_as_of']}")
    db.close()

    temp_path.replace(db_path)  # only replace the old database once the new one is complete
    print(f"Saved {db_path}")


if __name__ == "__main__":
    build()
