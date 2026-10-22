"""MCP server: exposes the stats functions as tools for Claude (Claude Code, Claude Desktop).

Each tool is a thin wrapper around tennis_scout.stats, so there is no stats logic here.
Run it with:  uv run python -m tennis_scout.mcp_server   (Claude Code starts it via .mcp.json)
"""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from tennis_scout import stats
# The report rules live in report.py, shared with the website. REPORT_SECTIONS is imported for the tests.
from tennis_scout.report import PERIOD, PERIOD_ARGS, REPORT_RULES, REPORT_SECTIONS, perspective  # noqa: F401


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
        extra_calls = (f"- head_to_head between {player} and {opponent} (with the surface filter if any, no dates)\n"
                       f"- matchup with player={player}, opponent={opponent} ({filters})\n"
                       f"- serve_stats and return_stats for {opponent} ({filters})\n")
    else:
        extra_calls = ""

    return f"""Write a scouting report on {player}, {"on " + surface if surface else "on all surfaces"}, \
for the period {PERIOD['label']}.
{perspective(player, opponent)}

First call find_player for each name and use the player_key it returns. Then call:
- serve_stats, return_stats and pressure_stats for {player} ({filters})
- the same three without the surface filter, to compare (same period)
{extra_calls}- recent_form for {player} (n=10)

{REPORT_RULES}"""


if __name__ == "__main__":
    server.run()  # stdio by default: Claude Code talks to the server through standard input/output
