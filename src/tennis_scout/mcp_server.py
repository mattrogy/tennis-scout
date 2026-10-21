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
2. Always call find_player first to get the player_key, then pass that key to the other tools.
3. With every stat, say how many matches it is based on (matches_used), and mention excluded matches if any.
4. Say that the data runs through May 2026 and that rankings are as of 8 June 2026.
5. Credit the data: Jeff Sackmann, CC BY-NC-SA 4.0.
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


if __name__ == "__main__":
    server.run()  # stdio by default: Claude Code talks to the server through standard input/output
