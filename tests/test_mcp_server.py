"""Tests for the MCP server: the tools Claude sees, and what they return.

They call the server directly (no Claude needed) and use the real database.
"""

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tennis_scout.db import DB_PATH
from tennis_scout.mcp_server import server

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="real database not built (run scripts/build_db.py)")


def call(tool, **arguments):
    """Call one tool the way Claude would, and return its structured answer."""
    result = asyncio.run(server.call_tool(tool, arguments))
    assert not result.is_error
    return result.structured_content


def test_all_tools_are_listed():
    tools = asyncio.run(server.list_tools())
    assert sorted(tool.name for tool in tools) == [
        "find_player", "head_to_head", "pressure_stats", "recent_form", "return_stats", "serve_stats",
    ]


def test_scout_report_prompt():
    prompts = asyncio.run(server.list_prompts())
    assert [prompt.name for prompt in prompts] == ["scout_report"]

    result = asyncio.run(server.get_prompt("scout_report", {"player": "Alcaraz", "opponent": "Sinner",
                                                            "surface": "Clay"}))
    text = result.messages[0].content.text
    assert "Alcaraz" in text and "Sinner" in text and "surface=Clay" in text
    assert "Every takeaway must cite the numbers" in text
    assert "Do not invent" in text
    assert "Do not count items in a list yourself" in text
    # The perspective must be unambiguous: the takeaways are for Sinner's coach, about Alcaraz.
    assert "The coach's player is Sinner. The player being scouted is Alcaraz." in text
    assert "Never decode a score string yourself" in text
    assert "serve_stats and return_stats for Sinner" in text
    assert "data through May 2026" in text
    assert "Tactical takeaways" in text and "Data caveats" in text


def test_new_tools_answer():
    alcaraz = "atp-207989"
    assert call("return_stats", player=alcaraz, surface="Clay")["matches_used"] > 0
    assert call("pressure_stats", player=alcaraz)["tie_breaks"]["played"] > 0
    assert len(call("recent_form", player=alcaraz, n=5)["matches"]) == 5


def test_find_player_then_serve_stats():
    sabalenka = call("find_player", name="sabalenka")["candidates"][0]
    assert sabalenka["name"] == "Aryna Sabalenka"

    result = call("serve_stats", player=sabalenka["player_key"], surface="Hard",
                  date_from="2025-01-01", date_to="2025-12-31")
    assert result["matches_used"] > 0
    assert "Jeff Sackmann" in result["source"]
    assert result["data_note"].startswith("Data through May 2026")


def test_errors_reach_claude_as_readable_messages():
    # A plain Python error would reach Claude only as "Error executing tool"; ours must keep its message.
    with pytest.raises(ToolError, match="Use find_player first"):
        asyncio.run(server.call_tool("serve_stats", {"player": "atp-1"}))
    with pytest.raises(ToolError, match="Surface must be one of"):
        asyncio.run(server.call_tool("head_to_head", {"player_a": "atp-206173", "player_b": "atp-207989",
                                                      "surface": "Carpet"}))
