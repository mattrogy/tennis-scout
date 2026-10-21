"""MCP server: exposes the stats functions as tools for Claude (Claude Code, Claude Desktop).

Each tool is a thin wrapper around tennis_scout.stats, so there is no stats logic here.
Run it with:  uv run python -m tennis_scout.mcp_server   (Claude Code starts it via .mcp.json)
"""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from tennis_scout import stats


def _default_period():
    """The default report period (last 24 months of data), read from the database once at start-up."""
    try:
        return stats.default_report_period()
    except FileNotFoundError:  # database not built yet: the tools will explain that when called
        return {"date_from": None, "date_to": None, "label": "the last 24 months of data"}


PERIOD = _default_period()
PERIOD_ARGS = f"date_from={PERIOD['date_from']}, date_to={PERIOD['date_to']}"

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

# One set of rules for every scouting report, whether it comes from a free question or from the scout_report prompt.
REPORT_RULES = f"""\
HOW TO WRITE A SCOUTING REPORT
Perspective
- A scouting report is about the player the coach will face (the scouted player), written for the coach of
  their own player (the coach's player).
- If two players are named and it is not clear which one is the coach's own player, ask before writing.
Period
- Use the default period, {PERIOD['label']} ({PERIOD_ARGS}), for serve_stats, return_stats, pressure_stats and
  matchup, unless the user asks for another period. State the period in the Summary and in the Data caveats.
- head_to_head uses no date filter (all meetings since 2015). recent_form is the last 10 matches.
Sections, in this order (without a coach's player, write "No opponent given." under Head-to-head and Matchup):
""" + "\n".join(f"{number}. {section}" for number, section in enumerate(REPORT_SECTIONS, start=1)) + """
Numbers
- Every number must be copied from a tool answer. Do not invent, estimate, round differently or compute new numbers
  (no differences, no averages of your own).
- Do not count items in a list yourself (for example "how many matches had a tie-break"): only state counts that a tool
  gives. Do not describe how a match was played (for example "held serve easily") unless a tool number shows it.
- Never decode a score string yourself: scores are written from the winner's side. For tie-breaks and deciding sets,
  use the tiebreaks_won, tiebreak_summary, deciding_set_summary and went_to_deciding_set fields.
- Every takeaway must cite the numbers and match counts it is based on,
  for example "2nd serve points won 44.1% (31 matches on clay)".
Strengths and weaknesses
- Call something a strength or a weakness only if its label in compared_to_tour says "strength" or "weakness".
  Cite the value, the percentile, the number of peers and the match count, for example
  "return points won vs 1st serve 37.4%, 99th percentile of 309 players (126 matches)".
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

INSTRUCTIONS = f"""\
You are a tennis scouting assistant for coaches.
General rules:
1. Every number you give must come from these tools. Never invent, estimate or calculate a statistic yourself.
2. Always call find_player first to get the player_key, then pass that key to the other tools.
3. With every stat, say how many matches it is based on (matches_used), and mention excluded matches if any.
4. Say that the data runs through May 2026 and that rankings are as of 8 June 2026.
5. Credit the data: Jeff Sackmann, CC BY-NC-SA 4.0.
Tools: find_player, head_to_head, serve_stats, return_stats, pressure_stats, recent_form, matchup.
Coverage: ATP and WTA tour-level matches since 2015. No live data, no betting advice.

For ANY request to scout, analyse or prepare against a player (with or without the scout_report prompt),
follow these rules:
{REPORT_RULES}"""

server = MCPServer(name="tennis-scout", instructions=INSTRUCTIONS)


def _run(function, **arguments):
    """Call a stats function; turn our expected errors into messages Claude can read."""
    try:
        return function(**arguments)
    except (stats.StatsError, FileNotFoundError) as error:
        raise ToolError(str(error)) from error


@server.tool()
def find_player(name: str, tour: str | None = None) -> dict[str, Any]:
    """Find ATP/WTA players by name (accents and capitals ignored).

    Returns candidates with their player_key (needed by the other tools), tour, country,
    current ranking (as of 8 June 2026) and number of tour-level matches since 2015.
    tour: optional, 'atp' or 'wta'.
    """
    return _run(stats.find_player, name=name, tour=tour)


@server.tool()
def head_to_head(
    player_a: str,
    player_b: str,
    surface: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Head-to-head record between two players, with the list of all their matches since 2015, and decoded
    tie-breaks and deciding sets for each player.

    player_a, player_b: player_keys from find_player (e.g. 'atp-207989').
    surface: optional, 'Hard', 'Clay' or 'Grass'. date_from / date_to: optional, 'YYYY-MM-DD'.
    Walkovers are listed but not counted as wins; retirements count.
    """
    return _run(stats.head_to_head, player_a=player_a, player_b=player_b,
                surface=surface, date_from=date_from, date_to=date_to)


@server.tool()
def serve_stats(
    player: str,
    surface: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Serve statistics for one player: 1st serve in %, 2nd serve in %, 1st and 2nd serve points won %,
    aces and double faults per match, break points saved %, plus the raw totals and the number of matches used.
    compared_to_tour gives, for each stat, the tour average, the percentile among peers and a label
    (strength / average / weakness / not enough data / not enough peers).

    player: player_key from find_player. surface: optional, 'Hard', 'Clay' or 'Grass'.
    date_from / date_to: optional, 'YYYY-MM-DD' (dates are tournament start dates).
    """
    return _run(stats.serve_stats, player=player, surface=surface, date_from=date_from, date_to=date_to)


@server.tool()
def return_stats(
    player: str,
    surface: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Return statistics for one player: return points won % against the 1st serve and against the 2nd serve,
    and break points converted %, plus the raw totals, the number of matches used, and compared_to_tour
    (tour average, percentile, label) for each stat.

    player: player_key from find_player. surface: optional, 'Hard', 'Clay' or 'Grass'.
    date_from / date_to: optional, 'YYYY-MM-DD' (dates are tournament start dates).
    """
    return _run(stats.return_stats, player=player, surface=surface, date_from=date_from, date_to=date_to)


@server.tool()
def pressure_stats(
    player: str,
    surface: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Pressure record for one player: tie-breaks won/lost and deciding sets won/lost, read from the scores,
    with compared_to_tour (percentile and label; no tour average, since it is always 50%).

    Completed matches only; retirements, walkovers and Next Gen Finals are skipped and counted.
    player: player_key from find_player. surface: optional, 'Hard', 'Clay' or 'Grass'.
    date_from / date_to: optional, 'YYYY-MM-DD'.
    """
    return _run(stats.pressure_stats, player=player, surface=surface, date_from=date_from, date_to=date_to)


@server.tool()
def recent_form(player: str, n: int = 10) -> dict[str, Any]:
    """The player's last n tour-level matches (newest first): date, tournament, surface, opponent, score, W/L,
    retirement marks, decoded tie-breaks, the win/loss record, how many of them the player retired from,
    and the current ranking (as of 8 June 2026).

    player: player_key from find_player. n: how many matches, 1 to 50 (default 10).
    """
    return _run(stats.recent_form, player=player, n=n)


@server.tool()
def matchup(
    player: str,
    opponent: str,
    surface: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Side by side: each player's serve against the other player's return (1st serve points, 2nd serve points,
    break points), with values, match counts, percentiles and labels exactly as in serve_stats and return_stats.
    Nothing is subtracted or combined.

    player, opponent: player_keys from find_player (same tour). surface: optional, 'Hard', 'Clay' or 'Grass'.
    date_from / date_to: optional, 'YYYY-MM-DD'.
    """
    return _run(stats.matchup, player=player, opponent=opponent,
                surface=surface, date_from=date_from, date_to=date_to)


@server.prompt()
def scout_report(player: str, opponent: str | None = None, surface: str | None = None) -> str:
    """Build a scouting report on a player, for a coach preparing a match against them.

    player: the player being scouted (the opponent you will face).
    opponent: optional, the coach's own player (adds the head-to-head and the matchup).
    surface: optional, 'Hard', 'Clay' or 'Grass'.
    """
    filters = (f"surface={surface}, " if surface else "") + PERIOD_ARGS
    if opponent:
        perspective = (f"The coach's player is {opponent}. The player being scouted is {player}.\n"
                       f"Write everything for {opponent}'s coach: how {opponent} can play against {player}.")
        extra_calls = (f"- head_to_head between {player} and {opponent} (with the surface filter if any, no dates)\n"
                       f"- matchup with player={player}, opponent={opponent} ({filters})\n"
                       f"- serve_stats and return_stats for {opponent} ({filters})\n")
    else:
        perspective = (f"The player being scouted is {player}. Write everything for a coach preparing a match "
                       f"against {player}.")
        extra_calls = ""

    return f"""Write a scouting report on {player}, {"on " + surface if surface else "on all surfaces"}, \
for the period {PERIOD['label']}.
{perspective}

First call find_player for each name and use the player_key it returns. Then call:
- serve_stats, return_stats and pressure_stats for {player} ({filters})
- the same three without the surface filter, to compare (same period)
{extra_calls}- recent_form for {player} (n=10)

{REPORT_RULES}"""


if __name__ == "__main__":
    server.run()  # stdio by default: Claude Code talks to the server through standard input/output
