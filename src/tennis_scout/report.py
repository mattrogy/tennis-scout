"""Scouting reports: the shared rules, and the tool answers a report is written from.

Used by both the MCP server (Claude Code, Claude Desktop) and the website, so a report follows
the same rules and relies on the same numbers wherever it is written.
"""

from tennis_scout import stats


def _default_period(db_path=None):
    """The default report period (last 24 months of data), read from the database."""
    try:
        return stats.default_report_period(db_path)
    except FileNotFoundError:  # database not built yet: the tools will explain that when called
        return {"date_from": None, "date_to": None, "label": "the last 24 months of data"}


def period_args(period):
    """The period written as tool arguments, for example 'date_from=2024-06-01, date_to=2026-05-25'."""
    return f"date_from={period['date_from']}, date_to={period['date_to']}"


PERIOD = _default_period()
PERIOD_ARGS = period_args(PERIOD)

REPORT_SECTIONS = [
    "Summary: three lines a coach can read in ten seconds, including the period covered",
    "Serve (scouted player)",
    "Return (scouted player)",
    "Pressure (scouted player: tie-breaks and deciding sets)",
    "Strengths and weaknesses (scouted player, from the labels only)",
    "Head-to-head (all meetings since 2015)",
    "Matchup (from the matchup tool)",
    "Recent form (scouted player, last 10 matches, with the current ranking and its date)",
    "Tactical takeaways for the coach's player: 3 to 5 bullet points",
    "Data caveats",
]


def report_rules(period):
    """One set of rules for every scouting report, whatever the way in (free question, prompt, website)."""
    return f"""\
HOW TO WRITE A SCOUTING REPORT
Perspective
- A scouting report is about the player the coach will face (the scouted player), written for the coach of
  their own player (the coach's player).
- If two players are named and it is not clear which one is the coach's own player, ask before writing.
Period
- Use the default period, {period['label']} ({period_args(period)}), for serve_stats, return_stats, pressure_stats and
  matchup, unless the user asks for another period. State the period in the Summary and in the Data caveats.
- head_to_head uses no date filter (all meetings since 2015). recent_form is the last 10 matches.
Sections, in this order (without a coach's player, write "No opponent given." under Head-to-head and Matchup):
""" + "\n".join(f"{number}. {section}" for number, section in enumerate(REPORT_SECTIONS, start=1)) + """
Numbers
- Every number must be copied from a tool answer. Do not invent, estimate, round differently or compute new numbers
  (no differences, no averages of your own).
- Do not count items in a list yourself (for example "how many matches had a tie-break") and do not add numbers up
  (for example "4 of the 6 tie-breaks": use tiebreaks_played). Only state counts and totals that a tool gives.
  Do not describe how a match was played (for example "held serve easily") unless a tool number shows it.
- Data caveats must list the excluded matches of every player whose numbers appear in the report.
- Never decode a score string yourself: scores are written from the winner's side. For tie-breaks and deciding sets,
  use the tiebreaks_won, tiebreak_summary, deciding_set_summary and went_to_deciding_set fields.
- Every takeaway must cite the numbers and match counts it is based on,
  for example "2nd serve points won 44.1% (31 matches on clay)".
Strengths and weaknesses
- Call something a strength or a weakness only if its label in compared_to_tour says "strength" or "weakness".
  Build the Strengths and weaknesses section from labels_summary, which already groups the stats by label.
  Cite the value, the percentile, the number of peers and the match count, for example
  "return points won vs 1st serve 37.4%, 99th percentile of 309 players (126 matches)".
- Before writing "the only ...", "all ..." or "none ...", check it against labels_summary and say which answer
  it covers (for example "the only serve stat in the matchup labelled average").
- When a label is "not enough data" or "not enough peers", say so instead of judging the stat.
Matchup
- Matchup takeaways must come from the matchup tool, which places one player's serve next to the other's return.
  Do not build your own comparison from two separate tables.
Takeaways
- Takeaways are suggestions for the coach, not certainties. If a number is based on fewer than 10 matches,
  say it is a small sample.
- Before writing, check each takeaway against the numbers you received: a takeaway must not contradict them.
Data caveats must say
- the period used, and "data through May 2026" (rankings as of 8 June 2026);
- which matches were excluded and why;
- that percentiles compare with tour-level players who have at least 10 matches with the same filters;
- that these stats cannot show shot patterns (direction, rally length);
- the credit: data by Jeff Sackmann, CC BY-NC-SA 4.0.
"""


REPORT_RULES = report_rules(PERIOD)


def perspective(scouted, coach=None):
    """Who the report is about and who it is for, said plainly so the model cannot take the wrong camp."""
    if coach:
        return (f"The coach's player is {coach}. The player being scouted is {scouted}.\n"
                f"Write everything for {coach}'s coach: how {coach} can play against {scouted}.")
    return f"The player being scouted is {scouted}. Write everything for a coach preparing a match against {scouted}."


def gather_report_data(scouted, coach=None, surface=None, db_path=None):
    """Call every stats tool a report needs, with the same arguments as the scout_report prompt.

    scouted, coach: player_keys (coach is optional). surface: optional, 'Hard', 'Clay' or 'Grass'.
    Returns who is who, the period, and the list of tool answers. This function computes no number itself.
    """
    if coach == scouted:
        raise stats.StatsError("The scouted player and the coach's player must be two different players.")
    period = _default_period(db_path)
    dates = {"date_from": period["date_from"], "date_to": period["date_to"]}
    tool_answers = []

    def call(function, **arguments):
        tool_answers.append({
            "tool": function.__name__,
            "arguments": arguments,
            "answer": function(**arguments, db_path=db_path),
        })
        return tool_answers[-1]["answer"]

    # The scouted player: serve, return and pressure with the filters...
    scouted_player = call(stats.serve_stats, player=scouted, surface=surface, **dates)["player"]
    call(stats.return_stats, player=scouted, surface=surface, **dates)
    call(stats.pressure_stats, player=scouted, surface=surface, **dates)
    # ...and on all surfaces too, to compare (only needed when a surface was chosen).
    if surface:
        for function in (stats.serve_stats, stats.return_stats, stats.pressure_stats):
            call(function, player=scouted, **dates)

    coach_player = None
    if coach:
        call(stats.head_to_head, player_a=scouted, player_b=coach, surface=surface)  # no dates: all meetings
        call(stats.matchup, player=scouted, opponent=coach, surface=surface, **dates)
        coach_player = call(stats.serve_stats, player=coach, surface=surface, **dates)["player"]
        call(stats.return_stats, player=coach, surface=surface, **dates)

    call(stats.recent_form, player=scouted, n=10)

    return {
        "scouted_player": scouted_player,
        "coach_player": coach_player,
        "surface": surface,
        "period": period,
        "perspective": perspective(scouted_player["name"], coach_player["name"] if coach_player else None),
        "tool_answers": tool_answers,
    }
