# tennis-scout

**A scouting assistant for tennis coaches: a public website and my own MCP server, on one tested stats module.**

**Try it online: [tennis-scout-roan.vercel.app](https://tennis-scout-roan.vercel.app)** — pick the player you will face (and optionally your own player and a
surface), or simply type *"Alcaraz vs Sinner on clay, I coach Sinner"*, and get a 10-section scouting report in a few
seconds: serve, return, pressure, strengths and weaknesses against the tour, head-to-head, the serve-vs-return matchup,
recent form and tactical takeaways.

In Claude (Claude Code, Claude Desktop), the same report comes from the MCP server: ask *"scout Alcaraz on clay, my
player is Sinner"*. Every number comes from a database through tested tools, with the number of matches behind it.
**On the website, the AI cannot write a number or a fact at all**: code writes them, the AI only writes checked headlines.

**Data through May 2026** (ATP and WTA tour-level matches since 2015). Rankings as of 8 June 2026.

---

## The problem

Preparing a match against a tour player means hours spent digging through stats sites: serve and return numbers,
how the player handles tie-breaks, results on this surface, recent form. A general chatbot answers in seconds,
but it often makes numbers up, and you cannot tell which ones.

tennis-scout splits the work:
- **the tools** compute every number from the data, with the match counts behind it;
- **the AI** turns those numbers into a report a coach can read in two minutes, and cites them.

## Sample report

A real run of `/mcp__tennis-scout__scout_report Alcaraz Sinner Clay`: scouting **Alcaraz** for **Sinner's** coach,
on clay, over the default period. It is pasted unedited (only the headings were shifted down one level to fit this page).
Every number in it was checked against the tool answers (about 100 values: no error found).

<details>
<summary><b>Show the full report</b></summary>

### Scouting report: Carlos Alcaraz on clay
*For the coach of Jannik Sinner: how Sinner can play against Alcaraz*

#### 1. Summary
- **Period:** June 2024 – May 2026, on clay (34 matches used). The all-surface figures for the same period (138 matches) are shown alongside for comparison.
- On clay Alcaraz **returns at an elite level** (99th percentile against both the 1st and 2nd serve). His **1st serve points won is only tour-average** (38th percentile), and **aces are a weakness** (19th percentile).
- They have met 5 times on clay: Alcaraz leads **3–2**. Sinner won the most recent clay meeting (Monte Carlo final, 2026).

#### 2. Serve (Alcaraz)
| Stat | Clay (34 matches) | Clay pct (of 108) / label | All surfaces (138 matches) | All pct (of 172) / label |
|---|---|---|---|---|
| 1st serve in | 66.3% | 84 / strength | 64.9% | 76 / strength |
| 2nd serve in | 90.8% | 38 / average | 90.9% | 48 / average |
| 1st serve points won | 69.4% | 38 / average | 74.3% | 73 / average |
| 2nd serve points won | 56.2% | 95 / strength | 57.2% | 99 / strength |
| Aces per match | 2.7 | 19 / **weakness** | 5.7 | 41 / average |
| Double faults per match | 2.3 | 52 / average | 2.5 | 57 / average |
| Break points saved | 68.9% | 94 / strength | 67% | 90 / strength |

Tour averages on clay: 1st serve in 62.8%, 1st serve points won 69.4%, 2nd serve points won 50.7%, aces 4.3, break points saved 60.7%.

#### 3. Return (Alcaraz)
| Stat | Clay (34 matches) | Clay pct (of 108) / label | All surfaces (138 matches) | All pct (of 172) / label |
|---|---|---|---|---|
| Return points won vs 1st serve | 38.1% | 99 / strength | 34.3% | 99 / strength |
| Return points won vs 2nd serve | 55.7% | 99 / strength | 53.3% | 97 / strength |
| Break points converted | 44.7% | 87 / strength | 42.8% | 90 / strength |

Tour averages on clay: 30.6% vs 1st serve, 49.3% vs 2nd serve, 39.3% of break points converted.

#### 4. Pressure (Alcaraz)
| | Clay (34 matches) | All surfaces (138 matches) |
|---|---|---|
| Tie-breaks | 10 won, 5 lost (66.7%): 80th pct of 49, **strength** | 32 won, 24 lost (57.1%): 77th pct of 142, **strength** |
| Deciding sets | 6 won, 0 lost (100%): **"not enough data"** | 22 won, 7 lost (75.9%): 100th pct of 120, **strength** |

On clay, his deciding-set record can't be judged against the tour. Across all surfaces, deciding sets are a strength.

#### 5. Strengths and weaknesses (clay, from the labels only)
**Strengths**
- Return points won vs 1st serve: 38.1%, 99th percentile of 108 players (34 matches)
- Return points won vs 2nd serve: 55.7%, 99th percentile of 108 (34 matches)
- 2nd serve points won: 56.2%, 95th percentile of 108 (34 matches)
- Break points saved: 68.9%, 94th percentile of 108 (34 matches)
- Break points converted: 44.7%, 87th percentile of 108 (34 matches)
- 1st serve in: 66.3%, 84th percentile of 108 (34 matches)
- Tie-breaks won: 66.7%, 80th percentile of 49 (34 matches)

**Weakness**
- Aces per match: 2.7, 19th percentile of 108 (34 matches). Across all surfaces this stat is "average" (5.7, 41st percentile of 172, 138 matches), so it is a weakness on clay only.

**Not judged:** deciding sets on clay ("not enough data").

#### 6. Head-to-head (clay meetings since 2015)
- Alcaraz leads **3–2** (5 matches, small sample). Tie-breaks: Alcaraz 4, Sinner 2. Deciding sets: Alcaraz 2, Sinner 1.
  - Umag F 2022: Sinner won (tie-breaks won: Alcaraz 1), went to a deciding set
  - Roland Garros SF 2024: Alcaraz won, went to a deciding set
  - Rome F 2025: Alcaraz won (tie-breaks won: Alcaraz 1)
  - Roland Garros F 2025: Alcaraz won (tie-breaks won: Alcaraz 2, Sinner 1), went to a deciding set
  - Monte Carlo F 2026: **Sinner won** (tie-breaks won: Sinner 1)
- For context, on all surfaces Alcaraz leads **10–7** (17 matches).

#### 7. Matchup (clay, June 2024 – May 2026)
**When Alcaraz serves** (Alcaraz: 34 matches, Sinner: 30 matches)
| | Alcaraz serve | Sinner return |
|---|---|---|
| 1st serve points | 69.4% (38th pct, **average**) | 38.8% (100th, strength) |
| 2nd serve points | 56.2% (95th, strength) | 54.3% (96th, strength) |
| Break points | saved 68.9% (94th, strength) | converted 47.3% (95th, strength) |

**When Sinner serves**
| | Sinner serve | Alcaraz return |
|---|---|---|
| 1st serve points | 76.4% (95th pct, strength) | 38.1% (99th, strength) |
| 2nd serve points | 61.3% (100th, strength) | 55.7% (99th, strength) |
| Break points | saved 67.7% (91st, strength) | converted 44.7% (87th, strength) |

Also from Sinner's clay serve stats (30 matches): 1st serve in 61.2% (33rd percentile, average), 2nd serve in 96.1% (98th, strength), double faults 1 per match (98th, strength).

#### 8. Recent form (Alcaraz, last 10 matches, all surfaces)
- Record **6–3** from 9 matches counted. One walkover is listed but not counted (Barcelona R16, April 2026, vs Machac). He retired from 0 of the last 10.
- Ranking: **No. 2**, 9,960 points (as of 8 June 2026).
- Losses: Sinner (Monte Carlo F, clay), Korda (Miami R32), Medvedev (Indian Wells SF).
- The most recent match in the data is Barcelona, week of 13 April 2026.

#### 9. Tactical takeaways for Sinner
These are suggestions, not certainties.
1. **Go after the Alcaraz 1st serve.** On clay it is his only serve stat in the matchup labelled "average": 1st serve points won 69.4%, 38th percentile (34 matches). Sinner's return vs the 1st serve is 38.8%, 100th percentile (30 matches).
2. **Expect long service games from him.** Aces are a clay weakness for Alcaraz: 2.7 per match, 19th percentile (34 matches). Few points will end on his serve alone, which gives Sinner's return chances to play.
3. **Keep the 2nd serve safe, and look for more 1st serves.** Alcaraz wins 55.7% of return points vs the 2nd serve, 99th percentile (34 matches). Sinner's 2nd serve holds up: 61.3% won (100th percentile), 96.1% in and 1 double fault per match (30 matches). His 1st serve in is only 61.2% (33rd percentile, average), so landing more 1st serves (76.4% won, 95th percentile) would keep Alcaraz's return out of the 2nd-serve points.
4. **Plan to need several break points per break.** Alcaraz saves 68.9% on clay, 94th percentile (34 matches). Sinner converts 47.3%, 95th percentile (30 matches).
5. **Try to settle sets before tie-breaks and deciding sets.** On clay Alcaraz wins 66.7% of tie-breaks, 80th percentile (10 won, 5 lost, 34 matches). Across all surfaces his deciding sets are a strength: 75.9%, 100th percentile of 120 (138 matches). In their clay meetings he leads tie-breaks 4–2 (5 matches, small sample). Sinner did win the most recent one, at Monte Carlo 2026.

#### 10. Data caveats
- **Period:** June 2024 – May 2026 (date_from 2024-06-01, date_to 2026-05-25) for serve, return, pressure and matchup. Head-to-head covers every clay meeting since 2015 (no date filter). Recent form is the last 10 matches on all surfaces.
- Data runs through May 2026. Rankings are as of 8 June 2026.
- **Excluded matches:**
  - Alcaraz on clay: 36 found, 34 used (1 walkover, 1 retired or ended early).
  - Alcaraz on all surfaces: 143 found, 138 used (1 walkover, 4 retired or ended early).
  - Sinner on clay: 32 found, 30 used (2 had no usable stats).
- **Percentiles** compare each player with tour-level players who have at least 10 matches under the same filters.
- These stats can't show **shot patterns** (direction, rally length).
- Data by Jeff Sackmann, CC BY-NC-SA 4.0.

</details>

## How it works

```
 Sackmann CSV files            scripts/download_data.py    (pinned to one fixed version of the data)
 (archival mirror)                      │
                                        ▼
                               scripts/build_db.py         cleans: surfaces, levels, retirements,
                                        │                  impossible stats, out-of-scope events
                                        ▼
                               data/tennis.db  (SQLite)    61,810 matches, read-only at runtime
                                        │
                                        ▼
                               src/tennis_scout/stats.py   ALL the stats logic, one place, tested
                                        │
                     ┌──────────────────┴──────────────────┐
                     ▼                                     ▼
          src/tennis_scout/mcp_server.py           src/tennis_scout/web.py (FastAPI on Vercel)
          7 tools + scout_report prompt            sections.py: sections 2-8 and 10, written by code
                     │                             facts.py:    numbered verified facts
                     ▼                             headlines.py: AI headlines, checked by code
          Claude (Claude Code / Claude Desktop)              │
          writes the report, citing the numbers              ▼
                                                   public/: the page (form + plain-English box)
```

The MCP server and the website are thin layers over `stats.py`, so they can never disagree on a number.

## The website

**What a visitor does:** type a few letters of a name and pick the player from the list (the page sends player keys,
never free text, to the report), or describe the match in one sentence (English or French); the form is filled in for
them to check, and nothing runs until they click **Scout**.

**How a report is built** (one request, about 3 to 6 seconds):

1. The same tested functions as the MCP server gather every number (`report.py`).
2. **Code writes sections 2 to 8 and 10** straight from those numbers: tables, head-to-head, matchup, recent form,
   caveats (`sections.py`).
3. Code turns the numbers into a **numbered list of verified fact sentences**, with label counts and tactical angles
   (where one player's strength meets the other's weakness) (`facts.py`).
4. **One call to Mistral Medium 3.5** returns JSON only: short headlines **with no numbers**, each citing fact IDs.
5. **Code checks every headline** (`headlines.py`): no digits, no sweeping words (every, never...), no stretched
   percentiles (elite, best...), no shot advice, no other player's name, the cited facts must exist, and its
   **direction must match the labels it cites** ("target" needs a weakness of the scouted player, "rely on" a strength
   of your player...). A failing headline is replaced by a plain code-written one, and logged.
6. Each headline is shown with its cited facts **copied word for word**, and a final check confirms that every number
   in the report exists in the statistics ("Numbers check: OK" on the page).

**Why this design:** five rounds of testing on the same 6 cases, every report read by hand. When the model wrote
the report itself, wrong facts came back every time (counts it made, sequences like "won their last two meetings",
"every stat is a strength"), even with strict rules. Once the model could only write headlines over code-written
facts, **wrong facts went to zero**, and the direction rules brought misread headlines to zero too.
Five models were compared (Mistral Small 4, Large 4, Medium 3.5, Claude Haiku 5.5 and Sonnet 5.5); Mistral Medium 3.5
had the fewest misreads at half Sonnet's price, about **$0.005 per report**. Full story: [DECISIONS.md](DECISIONS.md),
entries 18 and 19.

**Safety and cost, for a public site run by one person:**

- **The visitor's text never reaches the report.** The plain-English box sends its text in a POST body (never in a
  URL, log or cache) to a separate, small call that only extracts names and a surface; code validates them against
  the database, the model's reply is never shown, and off-topic or injected text gets one polite message.
- **Spending has three independent limits:** a dedicated OpenRouter key with a **$5 credit limit** (the hard ceiling,
  stored only in Vercel's settings); a firewall rule allowing **10 requests per 10 minutes per IP**; and a one-day
  cache, so the same report asked twice costs nothing. Bad requests are refused before any model call.
- **Not listed by search engines:** the site is open to anyone with the link, but every answer says `noindex`.
- **The page is locked down:** the report is cleaned by DOMPurify before display, and a Content-Security-Policy lets
  the page run only its own script and two pinned libraries with integrity hashes.

## The tools and their formulas

All tools take a `player_key` from `find_player`. Surface filter: Hard, Clay or Grass. Period filter: `date_from`
and `date_to` (YYYY-MM-DD, tournament start dates).
**Percentages add up the points over all matches first, then divide**, the same way the ATP/WTA compute season stats.

| Tool | What it returns | Formula (from the match files) |
|---|---|---|
| `find_player` | Players matching a name (accents ignored), with tour, country and current rank | — |
| `head_to_head` | Wins for each player + every match between them | Retirements count as a win; walkovers are listed, not counted (official rule) |
| `serve_stats` | 1st serve in % | 1st serves in / serve points |
| | 2nd serve in % | (2nd serves − double faults) / 2nd serves, where 2nd serves = serve points − 1st serves in |
| | 1st / 2nd serve points won % | 1st serve points won / 1st serves in; 2nd serve points won / 2nd serves |
| | Aces and double faults per match | total / matches used |
| | Break points saved % | break points saved / break points faced |
| `return_stats` | Return points won vs 1st serve % | (opponent's 1st serves in − 1st serve points they won) / opponent's 1st serves in |
| | Return points won vs 2nd serve % | (opponent's 2nd serves − 2nd serve points they won) / opponent's 2nd serves |
| | Break points converted % | (opponent's break points faced − saved) / faced |
| `pressure_stats` | Tie-break record, deciding-set record | Read from the score text (e.g. `6-7(4) 7-6(3) 6-4`) |
| `recent_form` | Last N matches, W/L record, "retired in X of the last N", current ranking | — |
| `matchup` | One player's serve next to the other's return: 1st serve points, 2nd serve points, break points | Values copied from `serve_stats` / `return_stats`; nothing subtracted or combined |

Every answer also says how many matches were **found**, **used**, and **excluded, and why**
(walkover, retirement, no usable stats, Next Gen Finals rules), plus the data freshness and the credit.
Head-to-head and recent form also give **decoded tie-breaks** for each player, because scores are written from the
winner's side (`6-7(5)` in a match Sinner won means Alcaraz won that tie-break).

### Strengths and weaknesses: decided in code, not by the AI

Every serve, return and pressure stat comes with `compared_to_tour`:

- **tour average** for the same tour, surface and period (not for tie-breaks and deciding sets: always 50%);
- **percentile**: the share of other players with a worse value, among players with **at least 10 matches** behind the stat;
- **label**: `strength` (≥ 75th percentile), `weakness` (≤ 25th), `average`, `not enough data` (under 10 matches)
  or `not enough peers` (under **30** players to compare with). Every comparison shows how many peers it used.

A percentile is used rather than "X points above average" because each stat has its own natural spread.
`labels_summary` groups the stats by label, so the report copies strengths and weaknesses instead of picking them.

### The scouting report

The **`scout_report` prompt** (and, for free questions, the same rules in the server instructions) tells Claude
which tools to call and how to write 10 sections: summary, serve, return, pressure, strengths and weaknesses,
head-to-head, matchup, recent form, tactical takeaways for the coach's player, and data caveats.
The **default period is the last 24 months of data** (June 2024 – May 2026), stated in every report; head-to-head keeps
all meetings since 2015. The rules: copy numbers only from tool answers, never count or add up items yourself,
never decode a score, cite numbers and match counts for every takeaway, flag samples under 10 matches,
and **ask which player is the coach's** when it is unclear.

## Data: source, credit, licence, freshness

- **Author of the data:** [Jeff Sackmann](https://www.tennisabstract.com/), originally published in the
  `tennis_atp` and `tennis_wta` GitHub repositories (no longer online since 2026).
- **Where the files come from:** the archival mirror
  [Aneeshers/tennis-sackmann-archive](https://github.com/Aneeshers/tennis-sackmann-archive),
  pinned to commit `83733587353df8a41f2fd4f516147d5aa83f5a8d` (June 2026 snapshot).
- **Licence:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/):
  credit the author, non-commercial use only, share derived data under the same licence.
- **Freshness:** tournaments starting up to 25 May 2026 (Roland Garros 2026 results are included, but without serve
  stats). Rankings as of 8 June 2026. There is no Wimbledon or US Open 2026.
- **Scope:** ATP and WTA tour-level main draws since 2015, including Grand Slams, Davis Cup / Billie Jean King Cup,
  Olympics and team events. Excluded: qualifying, Challengers, ITF events, WTA 125, exhibitions, live data. No betting use.

The raw data is **not** stored in this repository. `scripts/download_data.py` downloads it.

## Key decisions

The full reasoning (choice, alternatives, why) is in [DECISIONS.md](DECISIONS.md). In short:

- **SQLite:** one file, no server, ships with Python, fast enough for about 62,000 matches.
- **Pinned mirror:** the original repositories disappeared, so downloads are locked to one version and can be reproduced.
- **One shared stats module:** the MCP server and the website call the same tested functions.
- **Strict exclusions, always shown:** retirements, walkovers and impossible stats are left out of percentages,
  and every answer says how many and why.
- **Readable data cleaning:** for example, the WTA code `W` means "WTA Finals" in 2015, nine real tour events in
  2021 and "WTA 125" in 2024, so the tournament name decides. A full scan of every year caught this.
- **The report is a prompt, the numbers are code:** the model writes, the tools count.
- **Percentiles, not gut feeling:** strengths and weaknesses come from a coded rule, with minimum sample sizes
  (10 matches, 30 peers).
- **On the website, code writes every fact:** the AI writes checked headlines only (see [The website](#the-website)).
- **The database is built during each deploy** from the pinned mirror, so neither the raw data nor `tennis.db` is ever
  in the repository.

### What testing the AI taught me

Each report was checked number by number against the tools. Across four rounds, **every number copied from a tool was
right**; every error appeared where the model had to work something out on its own:

| Round | Error found | Fix (in the tools, not just in the prompt) |
|---|---|---|
| 1 | Counted "3 of 5" meetings with a tie-break (it was 4) | Rule: never count items yourself; later, the tool gives the count |
| 2 | Read a tie-break backwards from a winner-side score; wrote the advice for the wrong camp | Tools decode tie-breaks per player; the prompt names the coach's player |
| 3 | A free question skipped the report rules entirely | The same rules now live in the server instructions, for every question |
| 4 | "The only average stat" (there were three); added up "6 tie-breaks" itself | `labels_summary` and `tiebreaks_played` in the tools |

The lesson: **a rule is not enough when the model has to interpret raw data. Move the interpretation into tested code.**
Details in [DECISIONS.md](DECISIONS.md) (entry 15).

## Limitations

- **Not live:** the data stops in May 2026, about five months before this project.
- **Totals only, no shot data:** the files give totals per match (serve, return, break points, score). They cannot show
  shot direction, rally length or patterns such as "serves wide on the deuce side". The Match Charting Project could add
  some of this later, with its limited coverage always shown.
- **Dates are tournament start weeks**, not the day of each match. The order of matches is still correct (round order).
- **The peer group is the whole tour:** percentiles compare with every tour-level player who has at least 10 matches,
  not only the top 50, so top players naturally rank high on most stats.
- **Some matches have no serve stats** (old Davis Cup, Roland Garros 2026, about 6% overall). They still count in records,
  head-to-heads and pressure stats.
- **In Claude (MCP), the AI follows rules, not guarantees:** the prompt forbids invented or computed numbers, and the
  tests check the tools, but a report should still be read with its cited numbers. On the website, facts are written by
  code, and the AI's headlines are checked by word rules: strict, so some fair headlines are replaced by plainer ones.
- **Names must be spelt correctly** in the plain-English box ("djokovich" is politely refused); the name search
  matches parts of names, not near-spellings.

## How to run it

You need [uv](https://docs.astral.sh/uv/) (it installs Python and the dependencies).

```bash
git clone https://github.com/mattrogy/tennis-scout.git
cd tennis-scout
uv sync                                    # install dependencies
uv run python scripts/download_data.py     # download the CSV files (about 25 MB)
uv run python scripts/build_db.py          # build data/tennis.db
uv run pytest                              # 150 tests (the page's JavaScript tests run too if Node is installed)
```

**The website, on your own computer:** put your OpenRouter key in a `.env` file (`OPENROUTER_API_KEY=...`, never
committed), then run `uv run fastapi dev src/tennis_scout/web.py` and open http://127.0.0.1:8000.
`uv run python scripts/check_reports.py` writes the 6 test reports with the website's model and checks them
(`--parse` checks the plain-English box on 9 phrasings).

**Claude Code:** the repository includes `.mcp.json`. Start `claude` in the project folder and approve the
`tennis-scout` server. Then ask a question, or run `/mcp__tennis-scout__scout_report`.

**Claude Desktop:** add this to `claude_desktop_config.json` (Settings → Developer → Edit Config), with your own paths.
Use the full path to `uv` (`which uv` prints it):

```json
{
  "mcpServers": {
    "tennis-scout": {
      "command": "/full/path/to/uv",
      "args": ["--directory", "/full/path/to/tennis-scout", "run", "python", "-m", "tennis_scout.mcp_server"]
    }
  }
}
```

## Licence

- **Code:** [MIT](LICENSE). You may reuse and adapt the code in this repository.
- **Data: not included.** The tennis data was compiled by Jeff Sackmann and stays under
  [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). It is downloaded by
  `scripts/download_data.py` and is not covered by the MIT licence.
- Statistics and reports produced from the data are derived from it, so share them under the same terms:
  credit Jeff Sackmann, non-commercial use only, same licence.

## Project structure

```
scripts/download_data.py      download the pinned CSV files
scripts/build_db.py           clean + load into SQLite
src/tennis_scout/db.py        database path, read-only connection, name normalisation
src/tennis_scout/stats.py     all stats functions
src/tennis_scout/mcp_server.py  MCP tools + scout_report prompt
src/tennis_scout/report.py    report rules, the tool calls a report needs, check_report
src/tennis_scout/sections.py  website: sections 2-8 and 10, written by code
src/tennis_scout/facts.py     website: numbered verified facts, label counts, tactical angles
src/tennis_scout/headlines.py website: the headline prompt, checks and replacements
src/tennis_scout/parse.py     website: the plain-English box (extraction + validation)
src/tennis_scout/llm.py       the one place that calls a model (OpenRouter), model name set once
src/tennis_scout/web.py       website API: /api/health, /api/players, /api/report, /api/parse
public/                       the page: index.html, style.css, app.js, answers.js
app.py, vercel.json           Vercel entrypoint and function settings
scripts/check_reports.py      writes and checks real reports and phrasings (testing only)
tests/                        hand-calculated checks on a tiny fake dataset + known real results
DECISIONS.md                  every key choice, with alternatives and reasons
```
