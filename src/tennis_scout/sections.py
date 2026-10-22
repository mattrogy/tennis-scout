"""Website reports: sections 2-8 and 10 written by code, straight from the tool answers.

No model is involved here, so these sections cannot contain an invented number. The model only
writes "1. Summary" and "9. Tactical takeaways", from the text these functions produce.
(The MCP report in Claude Code is different: there the model writes all 10 sections.)

Every number below is copied from a tool answer; the code never computes a new one.
"""

SERVE_NAMES = {
    "first_serve_in_pct": "1st serve in",
    "second_serve_in_pct": "2nd serve in",
    "first_serve_points_won_pct": "1st serve points won",
    "second_serve_points_won_pct": "2nd serve points won",
    "aces_per_match": "Aces per match",
    "double_faults_per_match": "Double faults per match",
    "break_points_saved_pct": "Break points saved",
}
RETURN_NAMES = {
    "return_points_won_vs_first_serve_pct": "Return points won vs 1st serve",
    "return_points_won_vs_second_serve_pct": "Return points won vs 2nd serve",
    "break_points_converted_pct": "Break points converted",
}
PRESSURE_NAMES = {"tie_breaks_won_pct": "Tie-breaks won", "deciding_sets_won_pct": "Deciding sets won"}
STAT_NAMES = {**SERVE_NAMES, **RETURN_NAMES, **PRESSURE_NAMES}

SMALL_SAMPLE = "**Small sample:** fewer than 10 matches."


# ---------------------------------------------------------------- small formatting helpers


def _value(stat, value):
    """69.4 -> '69.4%' for percentages; per-match numbers stay plain."""
    if value is None:
        return "–"
    return f"{value}%" if stat.endswith("_pct") else f"{value}"


def _ordinal(number):
    """84 -> '84th', 21 -> '21st'."""
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _comparison(compared):
    """'84th percentile of 108 players, strength', or just the label when there is no percentile."""
    if not compared or "label" not in compared:  # no usable stats at all for these filters
        return "–"
    if compared.get("percentile") is None:
        return compared["label"]
    return f"{_ordinal(compared['percentile'])} percentile of {compared['peers']} players, {compared['label']}"


def walkovers(count):
    """'1 walkover', '0 walkovers', '2 walkovers'."""
    return f"{count} walkover" if count == 1 else f"{count} walkovers"


def _no_wrap(text):
    """Keep a score or a date on one line, so a narrow table scrolls instead of splitting '6-7(5)' in two."""
    return f'<span class="nowrap">{text}</span>'


def _fold(summary, body):
    """A block the reader opens on click, so side tables do not make the report twice as long."""
    return f"<details><summary>{summary}</summary>\n\n{body}\n\n</details>"


def _surname(name):
    return name.split()[-1]


def _filter_label(answer):
    surface = answer["filters"].get("surface")
    return surface.lower() if surface else "all surfaces"


def _answers(data, tool, player_key=None, surface="any"):
    """The tool answers of one kind, optionally for one player and one surface filter."""
    found = []
    for entry in data["tool_answers"]:
        arguments = entry["arguments"]
        if entry["tool"] != tool:
            continue
        if player_key and arguments.get("player") != player_key:
            continue
        if surface != "any" and arguments.get("surface") != surface:
            continue
        found.append(entry["answer"])
    return found


def _used_line(answer):
    """'34 of 36 matches used. Excluded: 1 walkover, 1 retired or ended early, 0 with no usable stats.'"""
    excluded = answer["matches_excluded"]
    return (f"{answer['matches_used']} of {answer['matches_found']} matches used. Excluded: "
            f"{walkovers(excluded['walkover'])}, {excluded['retired_or_ended_early']} retired or ended early, "
            f"{excluded['no_usable_stats']} with no usable stats.")


def _stat_table(answer, values_key, names):
    """One table: each stat with its value, tour average, percentile and label."""
    if answer[values_key] is None:
        return answer.get("message", "No usable stats for these filters.")
    lines = ["| Stat | Value | Tour average | Compared with the tour |", "|---|---|---|---|"]
    for stat, name in names.items():
        compared = answer["compared_to_tour"].get(stat, {})
        lines.append(f"| {name} | {_value(stat, answer[values_key][stat])} | "
                     f"{_value(stat, compared.get('tour_average'))} | {_comparison(compared)} |")
    return "\n".join(lines)


def _per_filter(data, tool, render):
    """Render the scouted player's answers: the chosen surface first, then all surfaces (folded) if one was chosen."""
    scouted = data["scouted_player"]["player_key"]
    blocks = []
    for answer in _answers(data, tool, scouted):
        title = f"**{data['scouted_player']['name']}, {_filter_label(answer)}, {data['period']['label']}**"
        block = "\n\n".join(part for part in (title, render(answer),
                                                SMALL_SAMPLE if answer["small_sample"] else "") if part)
        if answer["filters"]["surface"] != data["surface"]:  # the all-surface comparison, when a surface was chosen
            block = _fold("Show the all-surface numbers, for comparison", block)
        blocks.append(block)
    return "\n\n".join(blocks)


# ---------------------------------------------------------------- the sections


def serve_section(data):
    body = _per_filter(data, "serve_stats",
                       lambda a: _stat_table(a, "serve", SERVE_NAMES) + "\n\n" + _used_line(a))
    return f"## 2. Serve ({data['scouted_player']['name']})\n\n{body}"


def return_section(data):
    body = _per_filter(data, "return_stats",
                       lambda a: _stat_table(a, "return", RETURN_NAMES) + "\n\n" + _used_line(a))
    return f"## 3. Return ({data['scouted_player']['name']})\n\n{body}"


def _pressure_table(answer):
    lines = ["| | Played | Won | Lost | Won % | Compared with the tour |", "|---|---|---|---|---|---|"]
    for key, stat, name in (("tie_breaks", "tie_breaks_won_pct", "Tie-breaks"),
                            ("deciding_sets", "deciding_sets_won_pct", "Deciding sets")):
        record = answer[key]
        lines.append(f"| {name} | {record['played']} | {record['won']} | {record['lost']} | "
                     f"{_value(stat, record['won_pct'])} | {_comparison(answer['compared_to_tour'].get(stat))} |")
    skipped = answer["matches_skipped"]
    reasons = [walkovers(skipped["walkover"]), f"{skipped['retired_or_ended_early']} retired or ended early"]
    if skipped["next_gen_finals_rules"]:  # only worth a mention when it happened
        reasons.append(f"{skipped['next_gen_finals_rules']} under Next Gen Finals rules")
    lines.append("")
    lines.append(f"{answer['matches_used']} of {answer['matches_found']} matches used (completed matches only). "
                 f"Skipped: {', '.join(reasons)}.")
    return "\n".join(lines)


def pressure_section(data):
    body = _per_filter(data, "pressure_stats", _pressure_table)
    return f"## 4. Pressure ({data['scouted_player']['name']}: tie-breaks and deciding sets)\n\n{body}"


def strengths_section(data):
    """From labels_summary only, with the report's own filter (the chosen surface, or all surfaces)."""
    scouted = data["scouted_player"]["player_key"]
    groups = {"strength": [], "weakness": [], "average": [], "not judged": []}
    for tool, values_key in (("serve_stats", "serve"), ("return_stats", "return"),
                             ("pressure_stats", None)):
        answer = _answers(data, tool, scouted, surface=data["surface"])[0]
        for label, stats in answer.get("labels_summary", {}).items():
            for stat in stats:
                compared = answer["compared_to_tour"].get(stat, {})
                if values_key:
                    value = answer[values_key][stat]
                else:  # pressure: the won % sits inside the tie_breaks / deciding_sets records
                    value = answer["tie_breaks" if stat == "tie_breaks_won_pct" else "deciding_sets"]["won_pct"]
                groups[label].append(f"- {STAT_NAMES[stat]}: {_value(stat, value)}, {_comparison(compared)} "
                                     f"({answer['matches_used']} matches)")
    titles = {"strength": "Strengths", "weakness": "Weaknesses", "average": "Average",
              "not judged": "Not judged (not enough data or peers)"}
    parts = [f"## 5. Strengths and weaknesses ({data['scouted_player']['name']}, "
             f"{(data['surface'] or 'all surfaces').lower()}, based on the percentiles)"]
    for label, title in titles.items():
        parts.append(f"**{title}**\n\n" + ("\n".join(groups[label]) if groups[label] else "- None."))
    return "\n\n".join(parts)


def head_to_head_section(data):
    title = "## 6. Head-to-head (all meetings since 2015"
    title += f", {data['surface'].lower()})" if data["surface"] else ")"
    if not data["coach_player"]:
        return f"{title}\n\nNo opponent given."
    answer = _answers(data, "head_to_head")[0]
    if not answer["matches"]:
        return f"{title}\n\n{answer['message']}"
    a, b = answer["player_a"]["name"], answer["player_b"]["name"]
    tiebreaks, deciding = answer["tiebreak_summary"], answer["deciding_set_summary"]
    lines = [
        title, "",
        f"- **Wins:** {a} {answer['wins'][a]}, {b} {answer['wins'][b]} ({answer['matches_used']} matches counted, "
        f"{answer['matches_listed']} listed; walkovers are listed but not counted).",
        f"- **Tie-breaks:** {tiebreaks['tiebreaks_played']} played in {tiebreaks['matches_with_a_tiebreak']} matches; "
        f"won: {a} {tiebreaks['tiebreaks_won'][a]}, {b} {tiebreaks['tiebreaks_won'][b]}.",
        f"- **Deciding sets:** {deciding['matches_that_went_to_a_deciding_set']} matches went to a deciding set; "
        f"won: {a} {deciding['deciding_sets_won'][a]}, {b} {deciding['deciding_sets_won'][b]}.",
    ]
    recent = answer["most_recent_meeting"]
    lines.append(f"- **Most recent meeting:** {recent['tournament']} {recent['round']}, {recent['date']}, "
                 f"won by {recent['winner']}.")
    if answer["small_sample"]:
        lines += ["", SMALL_SAMPLE]
    lines += ["", f"| Week | Tournament | Round | Surface | Winner | Score | Tie-breaks won | Deciding set |",
              "|---|---|---|---|---|---|---|---|"]
    for m in answer["matches"]:
        won = ", ".join(f"{_surname(name)} {count}" for name, count in m["tiebreaks_won"].items())
        finish = "" if m["finish"] == "completed" else f" ({m['finish']})"
        lines.append(f"| {_no_wrap(m['date'])} | {m['tournament']} | {m['round']} | {m['surface']} | {m['winner']} | "
                     f"{_no_wrap(m['score'])}{finish} | {won} | {'yes' if m['went_to_deciding_set'] else 'no'} |")
    lines += ["", "Scores are written from the winner's side."]
    return "\n".join(lines)


def matchup_section(data):
    title = f"## 7. Matchup ({(data['surface'] or 'all surfaces').lower()}, {data['period']['label']})"
    if not data["coach_player"]:
        return f"{title}\n\nNo opponent given."
    answer = _answers(data, "matchup")[0]
    parts = [title, "Each number is that player's own number **against all opponents**, placed side by side. "
                    "These are not results of matches between the two players."]
    for key, pairs in answer.items():
        if not key.startswith("when "):
            continue
        server, returner = pairs[0]["server"]["name"], pairs[0]["returner"]["name"]
        lines = [f"**{key[0].upper() + key[1:]}**", "",
                 f"| | {server} (serve) | {returner} (return) |", "|---|---|---|"]
        for pair in pairs:
            cells = []
            for side in (pair["server"], pair["returner"]):
                cell = (f"{STAT_NAMES[side['stat']]} {_value(side['stat'], side['value'])}, "
                        f"{_comparison(side)} ({side['matches_used']} matches")
                cell += ", small sample)" if side["small_sample"] else ")"
                cells.append(cell)
            lines.append(f"| {pair['about'][0].upper() + pair['about'][1:]} | {cells[0]} | {cells[1]} |")
        parts.append("\n".join(lines))
    # The coach's player's own full serve and return numbers (folded: the pairs above already show the key ones).
    coach = data["coach_player"]
    own = []
    for tool, values_key, names in (("serve_stats", "serve", SERVE_NAMES), ("return_stats", "return", RETURN_NAMES)):
        coach_answer = _answers(data, tool, coach["player_key"])[0]
        own.append(f"**{coach['name']}'s own {values_key} ({_filter_label(coach_answer)})**\n\n"
                   + _stat_table(coach_answer, values_key, names) + "\n\n" + _used_line(coach_answer)
                   + ("\n\n" + SMALL_SAMPLE if coach_answer["small_sample"] else ""))
    parts.append(_fold(f"Show {coach['name']}'s own serve and return numbers", "\n\n".join(own)))
    return "\n\n".join(parts)


def recent_form_section(data):
    answer = _answers(data, "recent_form")[0]
    ranking, summary = answer["current_ranking"], answer["summary"]
    rank = (f"No. {ranking['rank']} ({ranking['points']} points)" if ranking["points"] is not None
            else f"{ranking['rank']}")
    lines = [
        f"## 8. Recent form ({data['scouted_player']['name']}, last {len(answer['matches'])} matches, "
        f"all surfaces)", "",
        f"- **Current ranking:** {rank}, as of {ranking['as_of']}.",
        f"- **Record:** {summary['wins']} wins, {summary['losses']} losses ({answer['matches_used']} matches counted; "
        f"{walkovers(summary['walkovers_listed_not_counted'])} listed, not counted). {summary['retired_text']}",
        f"- **Deciding sets:** {summary['matches_that_went_to_a_deciding_set']} of these matches went to a deciding "
        f"set. **Tie-breaks:** {summary['matches_with_a_tiebreak']} had a tie-break.",
        "",
        "| Week | Tournament | Surface | Round | Opponent (rank then) | Result | Score | Note |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in answer["matches"]:
        rank_then = m["opponent_rank_at_the_time"] if m["opponent_rank_at_the_time"] is not None else "–"
        lines.append(f"| {_no_wrap(m['date'])} | {m['tournament']} | {m['surface']} | {m['round']} | {m['opponent']} "
                     f"({rank_then}) | {m['result']} | {_no_wrap(m['score'])} | {m['note'] or ''} |")
    lines += ["", "'ret.' = the opponent retired; 'retired' = this player retired. Scores are written from the "
                  "winner's side."]
    return "\n".join(lines)


def caveats_section(data):
    period = data["period"]
    first = data["tool_answers"][0]["answer"]
    rankings_as_of = _answers(data, "recent_form")[0]["current_ranking"]["as_of"]
    lines = ["## 10. Data caveats", "",
             f"- **Period:** {period['label']} ({period['date_from']} to {period['date_to']}) for serve, return, "
             f"pressure and matchup. Head-to-head: all meetings since 2015. Recent form: the last matches listed.",
             f"- **Freshness:** {first['data_note']} Rankings as of {rankings_as_of}.",
             "- **Excluded matches:**"]
    for entry in data["tool_answers"]:
        if entry["tool"] == "serve_stats":  # serve and return use the same matches, so one line per player and filter
            answer = entry["answer"]
            lines.append(f"  - {answer['player']['name']}, {_filter_label(answer)}: {_used_line(answer)}")
    lines += [
        "- **Percentiles** compare each player with tour-level players who have at least 10 matches with the same "
        "filters.",
        "- These stats **cannot show shot patterns** (direction, rally length).",
        # No section numbers or model ID here: every number in a report must come from the tool answers.
        "- **How this report was made:** the Summary and the Tactical takeaways are written by an AI model from the "
        "other sections, and checked automatically. All other sections are written by code, straight from the "
        "statistics.",
        f"- **Data:** {first['source']} Reports are shared under the same licence, for non-commercial use.",
    ]
    return "\n".join(lines)


def render_sections(data):
    """Sections 2-8 and 10, as Markdown, keyed by section number."""
    return {
        2: serve_section(data),
        3: return_section(data),
        4: pressure_section(data),
        5: strengths_section(data),
        6: head_to_head_section(data),
        7: matchup_section(data),
        8: recent_form_section(data),
        10: caveats_section(data),
    }
