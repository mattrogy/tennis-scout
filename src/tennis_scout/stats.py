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
            SELECT tourney_date, tourney_name, level_name, surface, round, score, finish, won,
                   tiebreaks_won, tiebreaks_lost, deciding_set
            FROM player_matches
            WHERE player_key = ? AND opponent_key = ? {filter_sql}
            ORDER BY tourney_date, {ROUND_ORDER_SQL}
        """, [a["player_key"], b["player_key"]] + filter_values).fetchall()

        matches = []
        wins = {a["player_key"]: 0, b["player_key"]: 0}
        # Tie-break and deciding-set totals, from completed matches only (as in pressure_stats).
        tiebreaks = {a["name"]: 0, b["name"]: 0}
        deciding_sets = {a["name"]: 0, b["name"]: 0}
        matches_with_tiebreak = 0
        for row in rows:
            winner = a if row["won"] else b
            if row["finish"] != "walkover":
                wins[winner["player_key"]] += 1
            if row["finish"] == "completed":
                tiebreaks[a["name"]] += row["tiebreaks_won"]
                tiebreaks[b["name"]] += row["tiebreaks_lost"]
                matches_with_tiebreak += int(row["tiebreaks_won"] + row["tiebreaks_lost"] > 0)
                if row["deciding_set"]:
                    deciding_sets[winner["name"]] += 1
            matches.append({
                "date": _week_of(row["tourney_date"]),
                "tournament": row["tourney_name"],
                "level": row["level_name"],
                "surface": row["surface"] or "unknown",
                "round": row["round"],
                "winner": winner["name"],
                "score": row["score"],
                "finish": row["finish"],
                # Decoded from the score, so nobody has to read '6-7(5)' from the winner's side.
                "tiebreaks_won": {a["name"]: row["tiebreaks_won"], b["name"]: row["tiebreaks_lost"]},
                "went_to_deciding_set": bool(row["deciding_set"]),
            })

        completed = sum(1 for m in matches if m["finish"] == "completed")
        content = {
            "player_a": a,
            "player_b": b,
            "wins": {a["name"]: wins[a["player_key"]], b["name"]: wins[b["player_key"]]},
            "matches_used": sum(wins.values()),
            "matches_listed": len(matches),
            "tiebreak_summary": {
                "completed_matches": completed,
                "matches_with_a_tiebreak": matches_with_tiebreak,
                "tiebreaks_won": tiebreaks,
            },
            "deciding_set_summary": {
                "completed_matches": completed,
                "deciding_sets_won": deciding_sets,
            },
            "note": "Walkovers are listed but not counted as wins. Dates are tournament start weeks. "
                    "Scores are written from the winner's side: use the tiebreaks_won fields, not the score text.",
            "matches": matches,
        }
        return _result(db, content, filters)


# ---------------------------------------------------------------- point-based stats (serve, return)

# A match is "used" for point-based stats when it was completed and both players' serve numbers are valid.
USED_FOR_POINTS = "(finish = 'completed' AND stats_ok = 1)"
ENDED_EARLY = "finish IN ('retired', 'defaulted', 'abandoned')"

# The match counts every point-based answer carries: found, used, and why the others were left out.
POINT_COUNTS_SQL = f"""
    COUNT(*) AS found,
    SUM({USED_FOR_POINTS}) AS used,
    SUM(finish = 'walkover') AS walkovers,
    SUM({ENDED_EARLY}) AS ended_early,
    SUM(finish = 'completed' AND stats_ok = 0) AS no_stats"""


def _sum_used(column):
    """SQL that adds up one column over the used matches only."""
    return f'SUM(CASE WHEN {USED_FOR_POINTS} THEN "{column}" END)'


def _point_counts(row):
    return {
        "matches_found": row["found"],
        "matches_used": row["used"] or 0,
        "matches_excluded": {
            "walkover": row["walkovers"] or 0,
            "retired_or_ended_early": row["ended_early"] or 0,
            "no_usable_stats": row["no_stats"] or 0,
        },
    }


def serve_stats(player, surface=None, date_from=None, date_to=None, db_path=None):
    """Serve statistics for one player, added up over all matching matches.

    Percentages are total points / total points (not an average of per-match percentages).
    Only completed matches with usable stats are used; the others are counted and explained.
    """
    filters = _check_filters(surface, date_from, date_to)
    filter_sql, filter_values = _filter_sql(filters)

    with closing(connect(db_path)) as db:
        p = _get_player(db, player)
        row = db.execute(f"""
            SELECT {POINT_COUNTS_SQL},
                   {_sum_used("svpt")} AS serve_points,
                   {_sum_used("1stIn")} AS first_in,
                   {_sum_used("1stWon")} AS first_won,
                   {_sum_used("2ndWon")} AS second_won,
                   {_sum_used("ace")} AS aces,
                   {_sum_used("df")} AS double_faults
            FROM player_matches
            WHERE player_key = ? {filter_sql}
        """, [p["player_key"]] + filter_values).fetchone()

        content = {"player": p, **_point_counts(row)}
        matches_used = content["matches_used"]
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


def return_stats(player, surface=None, date_from=None, date_to=None, db_path=None):
    """Return statistics for one player, computed from the opponents' serve numbers.

    Same rules as serve_stats: points are added up first, then divided.
    """
    filters = _check_filters(surface, date_from, date_to)
    filter_sql, filter_values = _filter_sql(filters)

    with closing(connect(db_path)) as db:
        p = _get_player(db, player)
        row = db.execute(f"""
            SELECT {POINT_COUNTS_SQL},
                   {_sum_used("opp_svpt")} AS opp_serve_points,
                   {_sum_used("opp_1stIn")} AS opp_first_in,
                   {_sum_used("opp_1stWon")} AS opp_first_won,
                   {_sum_used("opp_2ndWon")} AS opp_second_won,
                   {_sum_used("opp_bpFaced")} AS break_points,
                   {_sum_used("opp_bpSaved")} AS break_points_saved_by_opponent
            FROM player_matches
            WHERE player_key = ? {filter_sql}
        """, [p["player_key"]] + filter_values).fetchone()

        content = {"player": p, **_point_counts(row)}
        if content["matches_used"] == 0:
            content["return"] = None
            content["message"] = "No completed match with usable stats for these filters."
            return _result(db, content, filters)

        # Every point the opponent did not win on serve was won by our player on return.
        # (Double faults count as return points won, as in official stats.)
        first_serve_returns = row["opp_first_in"]
        first_serve_returns_won = row["opp_first_in"] - row["opp_first_won"]
        second_serve_returns = row["opp_serve_points"] - row["opp_first_in"]
        second_serve_returns_won = second_serve_returns - row["opp_second_won"]
        break_points_won = row["break_points"] - row["break_points_saved_by_opponent"]
        content["return"] = {
            "return_points_won_vs_first_serve_pct": _percent(first_serve_returns_won, first_serve_returns),
            "return_points_won_vs_second_serve_pct": _percent(second_serve_returns_won, second_serve_returns),
            "break_points_converted_pct": _percent(break_points_won, row["break_points"]),
        }
        content["totals"] = {
            "first_serve_return_points": first_serve_returns,
            "first_serve_return_points_won": first_serve_returns_won,
            "second_serve_return_points": second_serve_returns,
            "second_serve_return_points_won": second_serve_returns_won,
            "break_points": row["break_points"],
            "break_points_won": break_points_won,
        }
        return _result(db, content, filters)


# ---------------------------------------------------------------- score-based stats (pressure, form)

# Next Gen Finals use sets to 4 games and no-ad scoring, so their tie-breaks and deciding sets are not comparable.
NEXT_GEN = "level_name = 'Next Gen Finals'"
USED_FOR_PRESSURE = f"(finish = 'completed' AND NOT {NEXT_GEN})"


def pressure_stats(player, surface=None, date_from=None, date_to=None, db_path=None):
    """Tie-break record and deciding-set record, read from the scores.

    Uses completed matches only (with or without serve stats). Retirements, walkovers and
    Next Gen Finals are skipped and counted.
    """
    filters = _check_filters(surface, date_from, date_to)
    filter_sql, filter_values = _filter_sql(filters)

    with closing(connect(db_path)) as db:
        p = _get_player(db, player)
        row = db.execute(f"""
            SELECT COUNT(*) AS found,
                   SUM({USED_FOR_PRESSURE}) AS used,
                   SUM(finish = 'walkover') AS walkovers,
                   SUM({ENDED_EARLY}) AS ended_early,
                   SUM(finish = 'completed' AND {NEXT_GEN}) AS next_gen,
                   SUM(CASE WHEN {USED_FOR_PRESSURE} THEN tiebreaks_won END) AS tiebreaks_won,
                   SUM(CASE WHEN {USED_FOR_PRESSURE} THEN tiebreaks_lost END) AS tiebreaks_lost,
                   SUM(CASE WHEN {USED_FOR_PRESSURE} THEN deciding_set END) AS deciding_sets,
                   SUM(CASE WHEN {USED_FOR_PRESSURE} AND deciding_set = 1 THEN won END) AS deciding_sets_won
            FROM player_matches
            WHERE player_key = ? {filter_sql}
        """, [p["player_key"]] + filter_values).fetchone()

        tiebreaks_won = row["tiebreaks_won"] or 0
        tiebreaks_lost = row["tiebreaks_lost"] or 0
        deciding_sets = row["deciding_sets"] or 0
        deciding_sets_won = row["deciding_sets_won"] or 0
        content = {
            "player": p,
            "matches_found": row["found"],
            "matches_used": row["used"] or 0,
            "matches_skipped": {
                "walkover": row["walkovers"] or 0,
                "retired_or_ended_early": row["ended_early"] or 0,
                "next_gen_finals_rules": row["next_gen"] or 0,
            },
            "tie_breaks": {
                "played": tiebreaks_won + tiebreaks_lost,
                "won": tiebreaks_won,
                "lost": tiebreaks_lost,
                "won_pct": _percent(tiebreaks_won, tiebreaks_won + tiebreaks_lost),
            },
            "deciding_sets": {
                "played": deciding_sets,
                "won": deciding_sets_won,
                "lost": deciding_sets - deciding_sets_won,
                "won_pct": _percent(deciding_sets_won, deciding_sets),
            },
            "note": "A deciding set is the last possible set (3rd of 3, 5th of 5). "
                    "A match tie-break such as [10-7] counts as a deciding set, not as a tie-break.",
        }
        return _result(db, content, filters)


def recent_form(player, n=10, db_path=None):
    """The player's last n matches (newest first), their record, and their current ranking."""
    if not isinstance(n, int) or not 1 <= n <= 50:
        raise StatsError("n must be a whole number between 1 and 50.")

    with closing(connect(db_path)) as db:
        p = _get_player(db, player)
        rows = db.execute(f"""
            SELECT tourney_date, tourney_name, level_name, surface, round,
                   opponent_name, opponent_rank, won, score, finish,
                   tiebreaks_won, tiebreaks_lost, deciding_set
            FROM player_matches
            WHERE player_key = ?
            ORDER BY tourney_date DESC, {ROUND_ORDER_SQL} DESC
            LIMIT ?
        """, (p["player_key"], n)).fetchall()

        matches = []
        for row in rows:
            if row["finish"] == "walkover":
                note = "w/o"
            elif row["finish"] == "retired":
                note = "ret." if row["won"] else "retired"  # "ret." = the opponent retired
            elif row["finish"] in ("defaulted", "abandoned"):
                note = row["finish"]
            else:
                note = None
            matches.append({
                "date": _week_of(row["tourney_date"]),
                "tournament": row["tourney_name"],
                "level": row["level_name"],
                "surface": row["surface"] or "unknown",
                "round": row["round"],
                "opponent": row["opponent_name"],
                "opponent_rank_at_the_time": row["opponent_rank"],
                "result": "W" if row["won"] else "L",
                "score": row["score"],
                "note": note,
                "tiebreaks_won": row["tiebreaks_won"],
                "tiebreaks_lost": row["tiebreaks_lost"],
                "went_to_deciding_set": bool(row["deciding_set"]),
            })

        played = [m for m in matches if m["note"] != "w/o"]
        retired_from = sum(1 for m in matches if m["note"] == "retired")
        ranking = db.execute("""
            SELECT rank, points FROM rankings
            WHERE player_key = ? AND ranking_date = (SELECT MAX(ranking_date) FROM rankings WHERE tour = ?)
        """, (p["player_key"], p["tour"])).fetchone()

        content = {
            "player": p,
            "current_ranking": {
                "rank": ranking["rank"] if ranking else "unranked",
                "points": ranking["points"] if ranking else None,
                "as_of": _freshness(db)["rankings_as_of"],
            },
            "matches_used": len(played),
            "summary": {
                "wins": sum(1 for m in played if m["result"] == "W"),
                "losses": sum(1 for m in played if m["result"] == "L"),
                "walkovers_listed_not_counted": len(matches) - len(played),
                "retired_from": retired_from,
                "retired_text": f"Retired in {retired_from} of the last {len(matches)} matches.",
            },
            "note": "'ret.' = the opponent retired; 'retired' = this player retired. Dates are tournament start weeks. "
                    "Scores are written from the winner's side: use the tiebreaks fields, not the score text.",
            "matches": matches,
        }
        return _result(db, content, {"last_n_matches": n})
