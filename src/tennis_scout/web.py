"""The website's API (FastAPI). Vercel runs it as one function; the page itself is public/index.html.

    GET /api/health                                   is the site working, and how fresh is the data
    GET /api/players?q=alca                           name search (no AI): candidates with their player_key
    GET /api/report?scouted=atp-207989&coach=atp-206173&surface=Clay
                                                      one scouting report (one model call, at most)

Visitors only send player keys and a surface picked from lists, so no visitor text ever reaches the model.
Run it locally with:  uv run fastapi dev src/tennis_scout/web.py
"""

import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from tennis_scout import llm, stats
from tennis_scout.facts import build_facts
from tennis_scout.headlines import RESPONSE_FORMAT, build_messages, write_sections
from tennis_scout.report import assemble_report, check_report, gather_report_data
from tennis_scout.sections import render_sections

app = FastAPI(title="tennis-scout", docs_url=None, redoc_url=None)  # no public API docs page

DB_PATH = None  # None = the default database (db.py); tests point it at a tiny fake one
write_report = llm.write_report  # the model call; tests replace it with a fake, so they need no network or key

PLAYER_KEY = re.compile(r"^(?:atp|wta)-\d{1,9}$")
MAX_SEARCH_LENGTH = 50
CACHE_ONE_DAY = "public, max-age=0, s-maxage=86400"  # the CDN keeps it for a day; the data only changes on redeploy
NO_STORE = "no-store"


def _answer(content, status=200, cache=False):
    """A JSON answer. Only good answers are cached; errors and failed checks never are."""
    return JSONResponse(content, status_code=status, headers={"Cache-Control": CACHE_ONE_DAY if cache else NO_STORE})


def _error(message, status):
    return _answer({"error": message}, status=status)


@app.get("/api/health")
def health():
    try:
        period = stats.default_report_period(db_path=DB_PATH)
    except FileNotFoundError:
        return _error("The database is missing.", 503)
    return _answer({"status": "ok", "data_through": period["date_to"], "default_period": period["label"],
                    "model": llm.MODEL})


@app.get("/api/players")
def players(q: str = ""):
    q = q.strip()
    if not q or len(q) > MAX_SEARCH_LENGTH:
        return _error(f"Type 1 to {MAX_SEARCH_LENGTH} characters of a player's name.", 400)
    try:
        found = stats.find_player(q, limit=8, db_path=DB_PATH)
    except stats.StatsError as error:
        return _error(str(error), 400)
    candidates = [{key: player[key] for key in ("player_key", "name", "tour", "country", "current_rank")}
                  for player in found["candidates"]]
    return _answer({"candidates": candidates}, cache=True)  # no AI involved: safe to cache


@app.get("/api/report")
def report(scouted: str = "", coach: str = "", surface: str = ""):
    coach, surface = coach or None, surface or None
    for label, key in (("scouted", scouted), ("coach", coach)):
        if key is not None and not PLAYER_KEY.match(key):
            return _error(f"'{label}' must be a player key such as atp-207989 (pick the player from the list).", 400)
    if surface is not None and surface not in stats.FILTER_SURFACES:
        return _error(f"Surface must be one of {', '.join(stats.FILTER_SURFACES)}, or left empty.", 400)

    try:
        data = gather_report_data(scouted, coach=coach, surface=surface, db_path=DB_PATH)
    except stats.StatsError as error:  # unknown player, same player twice, ATP against WTA
        return _error(str(error), 400)
    sections, facts = render_sections(data), build_facts(data)

    try:
        reply = write_report(build_messages(data, facts), response_format=RESPONSE_FORMAT)
    except llm.BudgetUsedUp:
        return _error("The report budget for this site is used up. Please try again later.", 503)
    except llm.ModelBusy:
        return _error("The model is busy right now. Please try again in a minute.", 503)
    except Exception as error:  # empty reply, timeout, network: say so plainly, never cache it
        print(f"model call failed: {type(error).__name__}")  # shows in the Vercel logs (no key, no visitor text)
        return _error("The report could not be written this time. Please try again.", 502)

    model_sections, replaced = write_sections(data, facts, reply["text"])
    for entry in replaced:  # logged so replacements can be reviewed later
        print(f"headline {entry['action']} ({entry['section']}): {entry['reason']}")
    print(f"report written: cost ${reply.get('cost_usd')}, {reply['input_tokens']}/{reply['output_tokens']} tokens")
    text = assemble_report({**sections, **model_sections})
    check = check_report(text, data)
    return _answer({
        "report": text,
        "check": check,
        "headlines_replaced": sum(1 for entry in replaced if entry["action"] == "replaced"),
        "model": llm.MODEL,
    }, cache=check["passed"])  # a report that fails the check is still shown (with a warning), never cached
