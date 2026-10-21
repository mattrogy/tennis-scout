"""All tennis statistics, in one place.

The MCP server (and later the website) only call these functions, so every number a user sees
comes from the same SQL queries. The AI never computes statistics itself.

Every result is a plain dict that includes:
  - the filters that were applied,
  - how many matches the numbers are based on,
  - how fresh the data is ("data through May 2026"),
  - the data credit (Jeff Sackmann, CC BY-NC-SA 4.0).
"""

from contextlib import closing
from datetime import date

from tennis_scout.db import connect, normalize_name

SOURCE_CREDIT = (
    "Data by Jeff Sackmann (tennis_atp / tennis_wta), via the Aneeshers/tennis-sackmann-archive mirror. "
    "Licence: CC BY-NC-SA 4.0."
)

# Surfaces a user can filter on. Carpet exists in the data (19 Davis Cup matches) but is not offered.
FILTER_SURFACES = ("Hard", "Clay", "Grass")
TOURS = ("atp", "wta")

# Sorts matches inside a tournament: a final comes after a semi-final, even with the same date.
ROUND_ORDER_SQL = """CASE round
    WHEN 'R128' THEN 1 WHEN 'R64' THEN 2 WHEN 'R32' THEN 3 WHEN 'R16' THEN 4
    WHEN 'RR' THEN 5 WHEN 'QF' THEN 6 WHEN 'SF' THEN 7 WHEN 'BR' THEN 8 WHEN 'F' THEN 9
    ELSE 0 END"""

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


class StatsError(ValueError):
    """A problem with the question (unknown player, bad filter). The message is shown to the user."""


# ---------------------------------------------------------------- helpers


def _percent(part, whole):
    """Percentage rounded to 1 decimal, or None when there is nothing to divide by."""
    if not whole:
        return None
    return round(100 * part / whole, 1)


def _per_match(total, matches):
    if not matches:
        return None
    return round(total / matches, 1)


def _week_of(iso_date):
    """'2025-05-26' -> 'week of 26 May 2025'. Sackmann dates are tournament start dates, not match days."""
    d = date.fromisoformat(iso_date)
    return f"week of {d.day} {MONTHS[d.month - 1]} {d.year}"


def _check_surface(surface):
    if surface is None:
        return None
    cleaned = surface.strip().title()
    if cleaned not in FILTER_SURFACES:
        raise StatsError(f"Surface must be one of {', '.join(FILTER_SURFACES)} (got {surface!r}).")
    return cleaned


def _check_date(label, value):
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise StatsError(f"{label} must be a date written YYYY-MM-DD (got {value!r}).") from None


def _check_filters(surface, date_from, date_to):
    filters = {
        "surface": _check_surface(surface),
        "date_from": _check_date("date_from", date_from),
        "date_to": _check_date("date_to", date_to),
    }
    if filters["date_from"] and filters["date_to"] and filters["date_from"] > filters["date_to"]:
        raise StatsError("date_from must be before date_to.")
    return filters


def _filter_sql(filters):
    """Turn the filters into SQL conditions on the player_matches view, with their values."""
    conditions, values = [], []
    if filters["surface"]:
        conditions.append("surface = ?")
        values.append(filters["surface"])
    if filters["date_from"]:
        conditions.append("tourney_date >= ?")
        values.append(filters["date_from"])
    if filters["date_to"]:
        conditions.append("tourney_date <= ?")
        values.append(filters["date_to"])
    sql = "".join(f" AND {condition}" for condition in conditions)
    return sql, values


def _get_player(db, player_key):
    row = db.execute("SELECT player_key, name, tour, country FROM players WHERE player_key = ?",
                     (player_key,)).fetchone()
    if row is None:
        raise StatsError(f"Unknown player_key {player_key!r}. Use find_player first to get the right key.")
    return dict(row)


def _freshness(db):
    """Data freshness labels, read from the database (set when it was built)."""
    meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
    through = date.fromisoformat(meta["data_through"])
    rankings = date.fromisoformat(meta["rankings_as_of"])
    return {
        "data_note": f"Data through {MONTHS[through.month - 1]} {through.year} "
                     f"(tournaments starting up to {meta['data_through']}).",
        "rankings_as_of": f"{rankings.day} {MONTHS[rankings.month - 1]} {rankings.year}",
    }


def _result(db, content, filters=None):
    """Add the shared fields every answer must carry."""
    freshness = _freshness(db)
    result = dict(content)
    if filters is not None:
        result["filters"] = filters
    result["data_note"] = freshness["data_note"]
    result["source"] = SOURCE_CREDIT
    return result


# ---------------------------------------------------------------- public functions


def find_player(name, tour=None, limit=10, db_path=None):
    """Find players whose name contains every word typed (accents and case ignored)."""
    words = normalize_name(name or "").split()
    if not words:
        raise StatsError("Please give at least part of a player's name.")
    if tour is not None and tour.lower() not in TOURS:
        raise StatsError("tour must be 'atp' or 'wta'.")

    conditions = " AND ".join("p.name_search LIKE ?" for _ in words)
    values = [f"%{word}%" for word in words]
    if tour:
        conditions += " AND p.tour = ?"
        values.append(tour.lower())

    with closing(connect(db_path)) as db:
        rows = db.execute(f"""
            SELECT p.player_key, p.name, p.tour, p.country, p.hand, p.birth_date,
                   (SELECT COUNT(*) FROM matches m WHERE m.winner_key = p.player_key)
                 + (SELECT COUNT(*) FROM matches m WHERE m.loser_key = p.player_key) AS matches_since_2015,
                   (SELECT r.rank FROM rankings r
                     WHERE r.player_key = p.player_key
                       AND r.ranking_date = (SELECT MAX(ranking_date) FROM rankings WHERE tour = p.tour)
                   ) AS current_rank
            FROM players p
            WHERE {conditions}
            ORDER BY (p.name_search = ?) DESC, matches_since_2015 DESC
            LIMIT ?
        """, values + [" ".join(words), limit]).fetchall()

        rankings_as_of = _freshness(db)["rankings_as_of"]
        candidates = []
        for row in rows:
            player = dict(row)
            player["current_rank"] = player["current_rank"] or "unranked"
            player["rank_as_of"] = rankings_as_of
            candidates.append(player)

        content = {"query": name, "candidates": candidates}
        if not candidates:
            content["message"] = "No tour-level player found since 2015 with that name."
        return _result(db, content)


def head_to_head(player_a, player_b, surface=None, date_from=None, date_to=None, db_path=None):
    """Every tour-level match between two players since 2015, and the win count.

    Walkovers are listed but not counted as wins (the official ATP/WTA rule). Retirements count.
    """
    filters = _check_filters(surface, date_from, date_to)
    filter_sql, filter_values = _filter_sql(filters)

    with closing(connect(db_path)) as db:
        a = _get_player(db, player_a)
        b = _get_player(db, player_b)
        if a["tour"] != b["tour"]:
            raise StatsError("The two players are on different tours (ATP and WTA), so they never met.")

        rows = db.execute(f"""
            SELECT tourney_date, tourney_name, level_name, surface, round, score, finish, won
            FROM player_matches
            WHERE player_key = ? AND opponent_key = ? {filter_sql}
            ORDER BY tourney_date, {ROUND_ORDER_SQL}
        """, [a["player_key"], b["player_key"]] + filter_values).fetchall()

        matches = []
        wins = {a["player_key"]: 0, b["player_key"]: 0}
        for row in rows:
            winner = a if row["won"] else b
            if row["finish"] != "walkover":
                wins[winner["player_key"]] += 1
            matches.append({
                "date": _week_of(row["tourney_date"]),
                "tournament": row["tourney_name"],
                "level": row["level_name"],
                "surface": row["surface"] or "unknown",
                "round": row["round"],
                "winner": winner["name"],
                "score": row["score"],
                "finish": row["finish"],
            })

        content = {
            "player_a": a,
            "player_b": b,
            "wins": {a["name"]: wins[a["player_key"]], b["name"]: wins[b["player_key"]]},
            "matches_used": sum(wins.values()),
            "matches_listed": len(matches),
            "note": "Walkovers are listed but not counted as wins. Dates are tournament start weeks.",
            "matches": matches,
        }
        return _result(db, content, filters)


def serve_stats(player, surface=None, date_from=None, date_to=None, db_path=None):
    """Serve statistics for one player, added up over all matching matches.

    Percentages are total points / total points (not an average of per-match percentages).
    Only completed matches with usable stats are used; the others are counted and explained.
    """
    filters = _check_filters(surface, date_from, date_to)
    filter_sql, filter_values = _filter_sql(filters)

    with closing(connect(db_path)) as db:
        p = _get_player(db, player)
        # "used" = completed matches with valid serve numbers; only those are added up.
        used = "(finish = 'completed' AND stats_ok = 1)"
        row = db.execute(f"""
            SELECT COUNT(*) AS found,
                   SUM({used}) AS used,
                   SUM(finish = 'walkover') AS walkovers,
                   SUM(finish IN ('retired', 'defaulted', 'abandoned')) AS ended_early,
                   SUM(finish = 'completed' AND stats_ok = 0) AS no_stats,
                   SUM(CASE WHEN {used} THEN "svpt" END) AS serve_points,
                   SUM(CASE WHEN {used} THEN "1stIn" END) AS first_in,
                   SUM(CASE WHEN {used} THEN "1stWon" END) AS first_won,
                   SUM(CASE WHEN {used} THEN "2ndWon" END) AS second_won,
                   SUM(CASE WHEN {used} THEN "ace" END) AS aces,
                   SUM(CASE WHEN {used} THEN "df" END) AS double_faults
            FROM player_matches
            WHERE player_key = ? {filter_sql}
        """, [p["player_key"]] + filter_values).fetchone()

        matches_used = row["used"] or 0
        content = {
            "player": p,
            "matches_found": row["found"],
            "matches_used": matches_used,
            "matches_excluded": {
                "walkover": row["walkovers"] or 0,
                "retired_or_ended_early": row["ended_early"] or 0,
                "no_usable_stats": row["no_stats"] or 0,
            },
        }
        if matches_used == 0:
            content["serve"] = None
            content["message"] = "No completed match with usable serve stats for these filters."
            return _result(db, content, filters)

        # Second serves played = serve points where the first serve missed.
        second_serves = row["serve_points"] - row["first_in"]
        content["serve"] = {
            "first_serve_in_pct": _percent(row["first_in"], row["serve_points"]),
            "second_serve_in_pct": _percent(second_serves - row["double_faults"], second_serves),
            "first_serve_points_won_pct": _percent(row["first_won"], row["first_in"]),
            "second_serve_points_won_pct": _percent(row["second_won"], second_serves),
            "aces_per_match": _per_match(row["aces"], matches_used),
            "double_faults_per_match": _per_match(row["double_faults"], matches_used),
        }
        # The raw totals behind the percentages, so anyone can check them.
        content["totals"] = {
            "serve_points": row["serve_points"],
            "first_serves_in": row["first_in"],
            "first_serve_points_won": row["first_won"],
            "second_serves": second_serves,
            "second_serve_points_won": row["second_won"],
            "aces": row["aces"],
            "double_faults": row["double_faults"],
        }
        return _result(db, content, filters)
