"""MCP server: exposes the stats functions as tools for Claude (Claude Code, Claude Desktop).

Each tool is a thin wrapper around tennis_scout.stats, so there is no stats logic here.
Run it with:  uv run python -m tennis_scout.mcp_server   (Claude Code starts it via .mcp.json)
"""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from tennis_scout import stats

INSTRUCTIONS = """\
You are a tennis scouting assistant for coaches. Rules:
1. Every number you give must come from these tools. Never invent, estimate or calculate a statistic yourself.
   This includes counting: do not count items in a list yourself (for example "4 of 5 matches had a tie-break");
   only state counts that appear in a tool answer.
   Do not describe how a match was played (for example "held serve easily") unless a tool number shows it.
2. Always call find_player first to get the player_key, then pass that key to the other tools.
3. With every stat, say how many matches it is based on (matches_used), and mention excluded matches if any.
4. Say that the data runs through May 2026 and that rankings are as of 8 June 2026.
5. Credit the data: Jeff Sackmann, CC BY-NC-SA 4.0.
Tools: find_player, head_to_head, serve_stats, return_stats, pressure_stats, recent_form.
For a full scouting report, follow the scout_report prompt.
Coverage: ATP and WTA tour-level matches since 2015. No live data, no betting advice.
"""

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
    """Head-to-head record between two players, with the list of all their matches since 2015.

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
    aces and double faults per match, plus the raw totals and the number of matches used.

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
    and break points converted %, plus the raw totals and the number of matches used.

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
    """Pressure record for one player: tie-breaks won/lost and deciding sets won/lost, read from the scores.

    Completed matches only; retirements, walkovers and Next Gen Finals are skipped and counted.
    player: player_key from find_player. surface: optional, 'Hard', 'Clay' or 'Grass'.
    date_from / date_to: optional, 'YYYY-MM-DD'.
    """
    return _run(stats.pressure_stats, player=player, surface=surface, date_from=date_from, date_to=date_to)


@server.tool()
def recent_form(player: str, n: int = 10) -> dict[str, Any]:
    """The player's last n tour-level matches (newest first): date, tournament, surface, opponent, score, W/L,
    retirement marks, the win/loss record, how many of them the player retired from, and the current ranking
    (as of 8 June 2026).

    player: player_key from find_player. n: how many matches, 1 to 50 (default 10).
    """
    return _run(stats.recent_form, player=player, n=n)


@server.prompt()
def scout_report(player: str, opponent: str | None = None, surface: str | None = None) -> str:
    """Build a scouting report on a player, for a coach preparing a match against them.

    player: the player being scouted (the opponent you will face).
    opponent: optional, the coach's own player (adds the head-to-head and matchup takeaways).
    surface: optional, 'Hard', 'Clay' or 'Grass'.
    """
    surface_text = f"on {surface}" if surface else "on all surfaces"
    surface_arg = f" with surface={surface}" if surface else ""
    if opponent:
        perspective = (f"The coach's player is {opponent}. The player being scouted is {player}.\n"
                       f"Write everything for {opponent}'s coach: how {opponent} can play against {player}.")
        extra_calls = (f"- head_to_head between {player} and {opponent}{surface_arg} (then once without the surface filter)\n"
                       f"- serve_stats and return_stats for {opponent}{surface_arg}, so matchup takeaways can cite "
                       f"numbers for both players\n")
    else:
        perspective = (f"The player being scouted is {player}. Write everything for a coach preparing a match "
                       f"against {player}.")
        extra_calls = ""

    return f"""Write a scouting report on {player}, {surface_text}.
{perspective}

First call find_player for each name and use the player_key it returns. Then call:
- serve_stats, return_stats and pressure_stats for {player}{surface_arg} (also once without the surface filter, to compare)
{extra_calls}- recent_form for {player} (n=10)

Use exactly these sections:
1. Summary: three lines a coach can read in ten seconds.
2. Serve ({player})
3. Return ({player})
4. Pressure ({player}: tie-breaks and deciding sets)
5. Head-to-head{"" if opponent else " (write 'No opponent given.')"}
6. Recent form ({player}, with the current ranking and its date)
7. Tactical takeaways for {opponent + "'s coach" if opponent else "the coach"}: 3 to 5 bullet points.
8. Data caveats

Rules:
- Every number must be copied from a tool answer. Do not invent, estimate, round differently or compute new numbers
  (no differences, no averages of your own).
- Do not count items in a list yourself (for example "how many matches had a tie-break"): only state counts that a tool
  gives. Do not describe how a match was played (for example "held serve easily") unless a tool number shows it.
- Never decode a score string yourself: scores are written from the winner's side. For tie-breaks and deciding sets,
  use the tiebreaks_won, tiebreak_summary, deciding_set_summary and went_to_deciding_set fields.
- A takeaway about a player must cite that player's own numbers: do not describe {opponent or "anyone"}'s serve using
  {player}'s return numbers.
- Every takeaway must cite the numbers and match counts it is based on,
  for example "2nd serve points won 44.1% (31 matches on clay)".
- Takeaways are suggestions for the coach, not certainties. If a number is based on fewer than 10 matches, say it is a small sample.
- Before writing, check each takeaway against the numbers you received: a takeaway must not contradict them.
- Data caveats must say: data through May 2026 (rankings as of 8 June 2026), which matches were excluded and why,
  that these stats cannot show shot patterns (direction, rally length), and the credit:
  data by Jeff Sackmann, CC BY-NC-SA 4.0.
"""


if __name__ == "__main__":
    server.run()  # stdio by default: Claude Code talks to the server through standard input/output
