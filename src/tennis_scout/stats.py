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
            "small_sample": sum(wins.values()) < MIN_MATCHES,
            "matches_listed": len(matches),
            # Copied from the last match in the list, so "who won the last meeting" never has to be worked out.
            "most_recent_meeting": {key: matches[-1][key] for key in ("date", "tournament", "round", "winner",
                                                                      "finish")} if matches else None,
            "tiebreak_summary": {
                "completed_matches": completed,
                "matches_with_a_tiebreak": matches_with_tiebreak,
                "tiebreaks_played": sum(tiebreaks.values()),
                "tiebreaks_won": tiebreaks,
            },
            "deciding_set_summary": {
                "completed_matches": completed,
                "matches_that_went_to_a_deciding_set": sum(deciding_sets.values()),
                "deciding_sets_won": deciding_sets,
            },
            "note": "Walkovers are listed but not counted as wins. Dates are tournament start weeks. "
                    "Scores are written from the winner's side: use the tiebreaks_won fields, not the score text.",
            "matches": matches,
        }
        if not matches:
            content["message"] = f"No meetings between {a['name']} and {b['name']} since 2015 with these filters."
        return _result(db, content, filters)


# ---------------------------------------------------------------- comparison with the tour

# A stat gets a label only if it is based on at least this many matches (tie-breaks / deciding sets for pressure).
MIN_MATCHES = 10  # also the "small_sample" threshold: under 10 matches, every answer says small_sample = true
# A percentile is given only if at least this many other players can be compared.
MIN_PEERS = 30
STRENGTH_PERCENTILE = 75
WEAKNESS_PERCENTILE = 25


def _place_among_peers(value, sample, peer_values, higher_is_better):
    """Percentile = share of the other players with a worse value. Returns {peers, percentile, label}."""
    result = {"peers": len(peer_values), "percentile": None}
    if value is None or sample < MIN_MATCHES:
        result["label"] = "not enough data"
    elif len(peer_values) < MIN_PEERS:
        result["label"] = "not enough peers"
    else:
        if higher_is_better:
            worse = sum(1 for peer in peer_values if peer < value)
        else:
            worse = sum(1 for peer in peer_values if peer > value)
        result["percentile"] = round(100 * worse / len(peer_values))
        if result["percentile"] >= STRENGTH_PERCENTILE:
            result["label"] = "strength"
        elif result["percentile"] <= WEAKNESS_PERCENTILE:
            result["label"] = "weakness"
        else:
            result["label"] = "average"
    return result


def _compare_to_tour(db, player, filters, select_sql, numbers, higher_is_better, show_tour_average=True):
    """Compare a player's numbers with every other player on the same tour, with the same filters.

    select_sql and numbers() are the same ones used for the player's own answer, so the player,
    the peers and the tour average are always computed the same way.
    """
    filter_sql, filter_values = _filter_sql(filters)
    values = [player["tour"]] + filter_values
    per_player = db.execute(f"""
        SELECT player_key, {select_sql} FROM player_matches
        WHERE tour = ? {filter_sql} GROUP BY player_key
    """, values).fetchall()
    whole_tour = numbers(db.execute(f"SELECT {select_sql} FROM player_matches WHERE tour = ? {filter_sql}",
                                    values).fetchone())

    mine = {"values": {}, "samples": {}}
    peers = []
    for row in per_player:
        if row["player_key"] == player["player_key"]:
            mine = numbers(row)
        else:
            peers.append(numbers(row))

    comparison = {}
    for stat, higher in higher_is_better.items():
        peer_values = [peer["values"][stat] for peer in peers
                       if peer["values"][stat] is not None and peer["samples"][stat] >= MIN_MATCHES]
        entry = {}
        if show_tour_average:
            entry["tour_average"] = whole_tour["values"][stat]
        entry.update(_place_among_peers(mine["values"].get(stat), mine["samples"].get(stat, 0), peer_values, higher))
        comparison[stat] = entry
    return comparison


def _labels_summary(comparison):
    """Group the stats by label, so a report can copy strengths and weaknesses instead of scanning for them."""
    groups = {"strength": [], "average": [], "weakness": [], "not judged": []}
    for stat, entry in comparison.items():
        groups.get(entry["label"], groups["not judged"]).append(stat)
    return groups


def _label_counts(groups):
    """How many stats carry each label, so "all", "none" or "only" claims can be checked against a number."""
    return {label: len(stats) for label, stats in groups.items()}


COMPARISON_NOTE = (
    f"Compared with the other players on the same tour, with the same filters, who have at least {MIN_MATCHES} "
    f"matches behind the stat. percentile = share of those players with a worse value. Labels: strength "
    f"(percentile >= {STRENGTH_PERCENTILE}), weakness (<= {WEAKNESS_PERCENTILE}), average (in between), "
    f"'not enough data' (under {MIN_MATCHES} matches), 'not enough peers' (under {MIN_PEERS} players to compare with)."
)


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


SERVE_SQL = f"""{POINT_COUNTS_SQL},
    {_sum_used("svpt")} AS serve_points,
    {_sum_used("1stIn")} AS first_in,
    {_sum_used("1stWon")} AS first_won,
    {_sum_used("2ndWon")} AS second_won,
    {_sum_used("ace")} AS aces,
    {_sum_used("df")} AS double_faults,
    {_sum_used("bpFaced")} AS break_points_faced,
    {_sum_used("bpSaved")} AS break_points_saved"""

# True = a higher value is better for the player.
SERVE_HIGHER_IS_BETTER = {
    "first_serve_in_pct": True,
    "second_serve_in_pct": True,
    "first_serve_points_won_pct": True,
    "second_serve_points_won_pct": True,
    "aces_per_match": True,
    "double_faults_per_match": False,
    "break_points_saved_pct": True,
}


def _serve_numbers(row):
    """The serve formulas, applied to one row of SERVE_SQL totals."""
    used = row["used"] or 0
    if used == 0:
        return {"values": dict.fromkeys(SERVE_HIGHER_IS_BETTER), "samples": dict.fromkeys(SERVE_HIGHER_IS_BETTER, 0)}
    # Second serves played = serve points where the first serve missed.
    second_serves = row["serve_points"] - row["first_in"]
    values = {
        "first_serve_in_pct": _percent(row["first_in"], row["serve_points"]),
        "second_serve_in_pct": _percent(second_serves - row["double_faults"], second_serves),
        "first_serve_points_won_pct": _percent(row["first_won"], row["first_in"]),
        "second_serve_points_won_pct": _percent(row["second_won"], second_serves),
        "aces_per_match": _per_match(row["aces"], used),
        "double_faults_per_match": _per_match(row["double_faults"], used),
        "break_points_saved_pct": _percent(row["break_points_saved"], row["break_points_faced"]),
    }
    return {"values": values, "samples": dict.fromkeys(values, used)}


def serve_stats(player, surface=None, date_from=None, date_to=None, db_path=None):
    """Serve statistics for one player, added up over all matching matches, and compared with the tour.

    Percentages are total points / total points (not an average of per-match percentages).
    Only completed matches with usable stats are used; the others are counted and explained.
    """
    filters = _check_filters(surface, date_from, date_to)
    filter_sql, filter_values = _filter_sql(filters)

    with closing(connect(db_path)) as db:
        p = _get_player(db, player)
        row = db.execute(f"SELECT {SERVE_SQL} FROM player_matches WHERE player_key = ? {filter_sql}",
                         [p["player_key"]] + filter_values).fetchone()

        content = {"player": p, **_point_counts(row)}
        content["small_sample"] = content["matches_used"] < MIN_MATCHES
        if content["matches_used"] == 0:
            content["serve"] = None
            content["message"] = "No completed match with usable serve stats for these filters."
            return _result(db, content, filters)

        content["serve"] = _serve_numbers(row)["values"]
        # The raw totals behind the percentages, so anyone can check them.
        content["totals"] = {
            "serve_points": row["serve_points"],
            "first_serves_in": row["first_in"],
            "first_serve_points_won": row["first_won"],
            "second_serves": row["serve_points"] - row["first_in"],
            "second_serve_points_won": row["second_won"],
            "aces": row["aces"],
            "double_faults": row["double_faults"],
            "break_points_faced": row["break_points_faced"],
            "break_points_saved": row["break_points_saved"],
        }
        content["compared_to_tour"] = _compare_to_tour(db, p, filters, SERVE_SQL, _serve_numbers,
                                                       SERVE_HIGHER_IS_BETTER)
        content["labels_summary"] = _labels_summary(content["compared_to_tour"])
        content["label_counts"] = _label_counts(content["labels_summary"])
        content["comparison_note"] = COMPARISON_NOTE
        return _result(db, content, filters)


RETURN_SQL = f"""{POINT_COUNTS_SQL},
    {_sum_used("opp_svpt")} AS opp_serve_points,
    {_sum_used("opp_1stIn")} AS opp_first_in,
    {_sum_used("opp_1stWon")} AS opp_first_won,
    {_sum_used("opp_2ndWon")} AS opp_second_won,
    {_sum_used("opp_bpFaced")} AS break_points,
    {_sum_used("opp_bpSaved")} AS break_points_saved_by_opponent"""

RETURN_HIGHER_IS_BETTER = {
    "return_points_won_vs_first_serve_pct": True,
    "return_points_won_vs_second_serve_pct": True,
    "break_points_converted_pct": True,
}


def _return_totals(row):
    """Every point the opponent did not win on serve was won by our player on return.
    (Double faults count as return points won, as in official stats.)"""
    return {
        "first_serve_return_points": row["opp_first_in"],
        "first_serve_return_points_won": row["opp_first_in"] - row["opp_first_won"],
        "second_serve_return_points": row["opp_serve_points"] - row["opp_first_in"],
        "second_serve_return_points_won": row["opp_serve_points"] - row["opp_first_in"] - row["opp_second_won"],
        "break_points": row["break_points"],
        "break_points_won": row["break_points"] - row["break_points_saved_by_opponent"],
    }


def _return_numbers(row):
    """The return formulas, applied to one row of RETURN_SQL totals."""
    used = row["used"] or 0
    if used == 0:
        return {"values": dict.fromkeys(RETURN_HIGHER_IS_BETTER), "samples": dict.fromkeys(RETURN_HIGHER_IS_BETTER, 0)}
    totals = _return_totals(row)
    values = {
        "return_points_won_vs_first_serve_pct": _percent(totals["first_serve_return_points_won"],
                                                         totals["first_serve_return_points"]),
        "return_points_won_vs_second_serve_pct": _percent(totals["second_serve_return_points_won"],
                                                          totals["second_serve_return_points"]),
        "break_points_converted_pct": _percent(totals["break_points_won"], totals["break_points"]),
    }
    return {"values": values, "samples": dict.fromkeys(values, used)}


def return_stats(player, surface=None, date_from=None, date_to=None, db_path=None):
    """Return statistics for one player, computed from the opponents' serve numbers, and compared with the tour.

    Same rules as serve_stats: points are added up first, then divided.
    """
    filters = _check_filters(surface, date_from, date_to)
    filter_sql, filter_values = _filter_sql(filters)

    with closing(connect(db_path)) as db:
        p = _get_player(db, player)
        row = db.execute(f"SELECT {RETURN_SQL} FROM player_matches WHERE player_key = ? {filter_sql}",
                         [p["player_key"]] + filter_values).fetchone()

        content = {"player": p, **_point_counts(row)}
        content["small_sample"] = content["matches_used"] < MIN_MATCHES
        if content["matches_used"] == 0:
            content["return"] = None
            content["message"] = "No completed match with usable stats for these filters."
            return _result(db, content, filters)

        content["return"] = _return_numbers(row)["values"]
        content["totals"] = _return_totals(row)
        content["compared_to_tour"] = _compare_to_tour(db, p, filters, RETURN_SQL, _return_numbers,
                                                       RETURN_HIGHER_IS_BETTER)
        content["labels_summary"] = _labels_summary(content["compared_to_tour"])
        content["label_counts"] = _label_counts(content["labels_summary"])
        content["comparison_note"] = COMPARISON_NOTE
        return _result(db, content, filters)


# ---------------------------------------------------------------- score-based stats (pressure, form)

# Next Gen Finals use sets to 4 games and no-ad scoring, so their tie-breaks and deciding sets are not comparable.
NEXT_GEN = "level_name = 'Next Gen Finals'"
USED_FOR_PRESSURE = f"(finish = 'completed' AND NOT {NEXT_GEN})"

PRESSURE_SQL = f"""
    COUNT(*) AS found,
    SUM({USED_FOR_PRESSURE}) AS used,
    SUM(finish = 'walkover') AS walkovers,
    SUM({ENDED_EARLY}) AS ended_early,
    SUM(finish = 'completed' AND {NEXT_GEN}) AS next_gen,
    SUM(CASE WHEN {USED_FOR_PRESSURE} THEN tiebreaks_won END) AS tiebreaks_won,
    SUM(CASE WHEN {USED_FOR_PRESSURE} THEN tiebreaks_lost END) AS tiebreaks_lost,
    SUM(CASE WHEN {USED_FOR_PRESSURE} THEN deciding_set END) AS deciding_sets,
    SUM(CASE WHEN {USED_FOR_PRESSURE} AND deciding_set = 1 THEN won END) AS deciding_sets_won"""

PRESSURE_HIGHER_IS_BETTER = {"tie_breaks_won_pct": True, "deciding_sets_won_pct": True}


def _pressure_numbers(row):
    """The pressure formulas. The sample behind each stat is the number of tie-breaks / deciding sets played."""
    tiebreaks = (row["tiebreaks_won"] or 0) + (row["tiebreaks_lost"] or 0)
    deciding_sets = row["deciding_sets"] or 0
    return {
        "values": {
            "tie_breaks_won_pct": _percent(row["tiebreaks_won"] or 0, tiebreaks),
            "deciding_sets_won_pct": _percent(row["deciding_sets_won"] or 0, deciding_sets),
        },
        "samples": {"tie_breaks_won_pct": tiebreaks, "deciding_sets_won_pct": deciding_sets},
    }


def pressure_stats(player, surface=None, date_from=None, date_to=None, db_path=None):
    """Tie-break record and deciding-set record, read from the scores, and compared with the tour.

    Uses completed matches only (with or without serve stats). Retirements, walkovers and
    Next Gen Finals are skipped and counted.
    """
    filters = _check_filters(surface, date_from, date_to)
    filter_sql, filter_values = _filter_sql(filters)

    with closing(connect(db_path)) as db:
        p = _get_player(db, player)
        row = db.execute(f"SELECT {PRESSURE_SQL} FROM player_matches WHERE player_key = ? {filter_sql}",
                         [p["player_key"]] + filter_values).fetchone()

        tiebreaks_won = row["tiebreaks_won"] or 0
        tiebreaks_lost = row["tiebreaks_lost"] or 0
        deciding_sets = row["deciding_sets"] or 0
        deciding_sets_won = row["deciding_sets_won"] or 0
        values = _pressure_numbers(row)["values"]
        # No tour average here: every tie-break has a winner and a loser, so it is always 50%.
        comparison = _compare_to_tour(db, p, filters, PRESSURE_SQL, _pressure_numbers,
                                      PRESSURE_HIGHER_IS_BETTER, show_tour_average=False)
        content = {
            "player": p,
            "matches_found": row["found"],
            "matches_used": row["used"] or 0,
            "small_sample": (row["used"] or 0) < MIN_MATCHES,
            "matches_skipped": {
                "walkover": row["walkovers"] or 0,
                "retired_or_ended_early": row["ended_early"] or 0,
                "next_gen_finals_rules": row["next_gen"] or 0,
            },
            "tie_breaks": {
                "played": tiebreaks_won + tiebreaks_lost,
                "won": tiebreaks_won,
                "lost": tiebreaks_lost,
                "won_pct": values["tie_breaks_won_pct"],
            },
            "deciding_sets": {
                "played": deciding_sets,
                "won": deciding_sets_won,
                "lost": deciding_sets - deciding_sets_won,
                "won_pct": values["deciding_sets_won_pct"],
            },
            "note": "A deciding set is the last possible set (3rd of 3, 5th of 5). "
                    "A match tie-break such as [10-7] counts as a deciding set, not as a tie-break.",
            "compared_to_tour": comparison,
            "labels_summary": _labels_summary(comparison),
            "label_counts": _label_counts(_labels_summary(comparison)),
            "comparison_note": COMPARISON_NOTE + " No tour average for pressure stats: it is always 50%, "
                               "because every tie-break and deciding set has one winner and one loser.",
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
                "matches_that_went_to_a_deciding_set": sum(1 for m in matches if m["went_to_deciding_set"]),
                "matches_with_a_tiebreak": sum(1 for m in matches if m["tiebreaks_won"] + m["tiebreaks_lost"] > 0),
            },
            "note": "'ret.' = the opponent retired; 'retired' = this player retired. Dates are tournament start weeks. "
                    "Scores are written from the winner's side: use the tiebreaks fields, not the score text.",
            "matches": matches,
        }
        return _result(db, content, {"last_n_matches": n})


# ---------------------------------------------------------------- matchup and report period

# (serve stat of the server, return stat of the returner, what the pair is about)
MATCHUP_PAIRS = [
    ("first_serve_points_won_pct", "return_points_won_vs_first_serve_pct", "points on 1st serve"),
    ("second_serve_points_won_pct", "return_points_won_vs_second_serve_pct", "points on 2nd serve"),
    ("break_points_saved_pct", "break_points_converted_pct", "break points"),
]


def _matchup_side(server, server_serve, returner, returner_return):
    """One serving direction: the server's serve numbers next to the returner's return numbers."""
    pairs = []
    for serve_stat, return_stat, about in MATCHUP_PAIRS:
        pairs.append({
            "about": about,
            "server": {
                "name": server["name"],
                "stat": serve_stat,
                "value": (server_serve["serve"] or {}).get(serve_stat),
                "matches_used": server_serve["matches_used"],
                "small_sample": server_serve["small_sample"],
                **server_serve.get("compared_to_tour", {}).get(serve_stat, {}),
            },
            "returner": {
                "name": returner["name"],
                "stat": return_stat,
                "value": (returner_return["return"] or {}).get(return_stat),
                "matches_used": returner_return["matches_used"],
                "small_sample": returner_return["small_sample"],
                **returner_return.get("compared_to_tour", {}).get(return_stat, {}),
            },
        })
    return pairs


def matchup(player, opponent, surface=None, date_from=None, date_to=None, db_path=None):
    """Side by side: each player's serve against the other's return, with the same filters.

    The values, percentiles and labels are exactly those of serve_stats and return_stats.
    No difference or 'edge' is computed: the numbers are placed next to each other.
    """
    arguments = {"surface": surface, "date_from": date_from, "date_to": date_to, "db_path": db_path}
    p_serve, p_return = serve_stats(player, **arguments), return_stats(player, **arguments)
    o_serve, o_return = serve_stats(opponent, **arguments), return_stats(opponent, **arguments)
    p, o = p_serve["player"], o_serve["player"]
    if p["tour"] != o["tour"]:
        raise StatsError("The two players are on different tours (ATP and WTA), so they never meet.")

    with closing(connect(db_path)) as db:
        content = {
            "player": p,
            "opponent": o,
            f"when {p['name']} serves": _matchup_side(p, p_serve, o, o_return),
            f"when {o['name']} serves": _matchup_side(o, o_serve, p, p_return),
            "note": "Each value is that player's own number against all opponents (with these filters), with its "
                    "match count, tour percentile and label, exactly as in serve_stats and return_stats. These are "
                    "NOT results of matches between these two players. Nothing is subtracted or combined.",
        }
        return _result(db, content, p_serve["filters"])


def default_report_period(db_path=None):
    """The default period for scouting reports: the last 24 months of data, ending with the latest data."""
    with closing(connect(db_path)) as db:
        through = date.fromisoformat(dict(db.execute("SELECT key, value FROM meta").fetchall())["data_through"])
    # 24 months including the last one: e.g. data through May 2026 -> June 2024 to May 2026.
    months = through.year * 12 + (through.month - 1) - 23
    start = date(months // 12, months % 12 + 1, 1)
    return {
        "date_from": start.isoformat(),
        "date_to": through.isoformat(),
        "label": f"{MONTHS[start.month - 1]} {start.year} – {MONTHS[through.month - 1]} {through.year}",
    }
