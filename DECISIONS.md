# Decisions

Each entry records **the choice**, **the alternatives** and **why**.

## 1. Data source: a pinned archival mirror of Jeff Sackmann's data
- **Choice:** download from [Aneeshers/tennis-sackmann-archive](https://github.com/Aneeshers/tennis-sackmann-archive),
  locked to commit `83733587353df8a41f2fd4f516147d5aa83f5a8d`. Credit Sackmann as author, the mirror as where the files come from.
- **Alternatives:** Sackmann's original `tennis_atp` / `tennis_wta` repositories; pause the project; another dataset.
- **Why:** the originals return 404 since around September 2026 and no official explanation was found.
  The mirror keeps the same files and the same CC BY-NC-SA 4.0 licence. Pinning one commit means anyone gets
  exactly the same files, so results and tests can be reproduced even if the mirror changes.

## 2. Storage: SQLite
- **Choice:** one local SQLite file, `data/tennis.db`, built from the CSVs.
- **Alternatives:** PostgreSQL; DuckDB; reading the CSVs with pandas on every question.
- **Why:** about 65,000 matches fit easily in one file. SQLite needs no server and no account, and ships with Python.
  The same file can be deployed with the website on Day 3. Postgres would add a server to run and pay for.
  DuckDB is great for analytics but is an extra dependency we don't need at this size. Re-reading CSVs on
  every question would be slow and would scatter the cleaning logic.

## 3. Python standard library instead of pandas
- **Choice:** `urllib`, `csv` and `sqlite3` for download and loading.
- **Alternatives:** pandas, requests.
- **Why:** fewer dependencies to install and explain. The stats are simple sums in SQL, so a dataframe library adds nothing.

## 4. Player key: tour + id (for example `atp-206173`)
- **Choice:** every player is identified by a text key combining tour and Sackmann's numeric id.
- **Alternatives:** the numeric id alone; the player's name.
- **Why:** ATP and WTA ids are separate numbering systems and can collide. Names are ambiguous and
  spelled in different ways. So `find_player` turns a name into a key, and every other tool takes the key.

## 5. Aggregation: sum the points, then divide
- **Choice:** "1st serve points won %" over 20 matches = total 1st-serve points won / total 1st serves in.
- **Alternatives:** average each match's percentage.
- **Why:** averaging percentages gives a 3-set match the same weight as a 5-set match.
  Summing points first is how the ATP and WTA compute season stats.

## 6. Retirements and walkovers are excluded from percentage stats
- **Choice:** they are left out of serve/return percentages, but kept in head-to-head lists and win/loss records
  (marked "ret." or "w/o").
- **Alternatives:** keep everything; drop them everywhere.
- **Why:** an injured player's half-match distorts percentages, and a walkover has no points at all.
  The result still happened, so it belongs in the head-to-head.
- **Head-to-head wins:** retirements count as a win (official ATP/WTA rule). Walkovers are listed but **not** counted,
  because no ball was played (also the official rule).

## 7. Tournament levels: mapped to readable names, out-of-scope events excluded
- **Choice:** map Sackmann's level codes to names (Grand Slam, Masters 1000, WTA 1000, ...).
  Exclude ITF events (codes `35+H`, `50+H`) and WTA 125 events. The build stops with an error on any unknown code.
- **Alternatives:** keep all rows; ignore the level.
- **Why:** the scope is tour-level matches. ITF events slipped into the WTA 2025 file (215 matches).
  WTA 125 is the equivalent of ATP Challengers, which are not loaded either. Stopping on unknown codes
  prevents silent mislabelling.
- **Code `W` is ambiguous, so the tournament name decides:** it means "WTA Finals" in 2015, nine real
  WTA 250/500 events in 2021 (Eastbourne, Strasbourg...), and "Buenos Aires 125" in 2024. Rule: name contains
  "Finals" → WTA Finals; contains "125" → excluded; otherwise → WTA 250/500 (kept). A first rule
  ("not Finals = WTA 125") would have wrongly removed 270 real tour matches. A full scan of all years caught it.

## 7b. Carpet: kept in records, not offered as a filter
- **Choice:** the 19 carpet matches (Davis Cup Group II ties, 2016–2017) stay in the database. The surface filter
  only accepts Hard, Clay and Grass. The same applies to the 168 matches with no surface recorded.
- **Alternatives:** delete them; allow a "Carpet" filter.
- **Why:** a result is a fact. Deleting it would quietly make some head-to-heads and records wrong.
  A carpet filter would always return an almost empty answer. These matches have no serve stats, so they never affect percentages.

## 8. Freshness labels on every answer
- **Choice:** every tool answer says "data through May 2026", and rankings say "as of 8 June 2026".
  Both dates are read from the database (built from the data), not typed by hand.
- **Alternatives:** no label; a note only in the README.
- **Why:** the snapshot is about 5 months old (no Wimbledon or US Open 2026). A coach must know that
  "recent form" stops in May, or they may prepare with outdated information.
- **Note on dates:** Sackmann gives each match the **tournament start date**, not the day it was played.
  So "data through 2026-05-25" means tournaments starting up to that date, including Roland Garros 2026
  (which ended in June). Date filters work on tournament start dates.

## 8b. "Usable stats" check
- **Choice:** a match counts for percentage stats only if both players' serve numbers are present and possible
  (serve points > 0, 1st serves in ≤ serve points, 1st serve points won ≤ 1st serves in,
  2nd serve points won + double faults ≤ 2nd serves, break points saved ≤ faced).
- **Alternatives:** trust every row.
- **Why:** about 320 player-match rows contain impossible numbers (for example, 0 serve points).
  They would distort percentages or cause a division by zero. Each answer counts them under "no usable stats".

## 9. One shared stats module
- **Choice:** all stats logic lives in `src/tennis_scout/stats.py`. The MCP server (and the website on Day 3)
  only call its functions.
- **Alternatives:** separate logic in the MCP server and in the web backend.
- **Why:** one place to test and fix. The Claude app and the website can never disagree on a number.

## 10. MCP server: official Python SDK (mcp 2.x), stdio transport
- **Choice:** `MCPServer` from the official `mcp` package (version 2.x; it was called `FastMCP` in version 1),
  running over stdio.
- **Alternatives:** the low-level MCP API; an HTTP transport.
- **Why:** the decorator style (`@server.tool()`) keeps each tool to a few readable lines. Stdio is what
  Claude Code and Claude Desktop use for local servers, so no port or authentication is needed.
- **Errors:** in mcp 2.x, an unexpected Python error reaches Claude only as "Error executing tool". So the server turns
  our expected errors (unknown player, bad surface or date) into `ToolError`, whose message Claude can read and act on
  (for example, "Use find_player first").

## 12. Pressure stats are read from the score text
- **Choice:** the build reads each score (for example `6-7(4) 7-6(3) 6-4`, written from the winner's side) and stores
  the tie-breaks won by each player, the number of sets, and whether the match went to a deciding set.
  `pressure_stats` then simply adds these up in SQL.
- **Alternatives:** parse scores at question time in Python.
- **Why:** the parsing is done once, tested on its own (`score_summary`), and the stats stay simple sums, like the others.
- **Special formats:**
  - `[10-7]` is a match tie-break played *instead of* a final set (Laver Cup, some Davis Cup, 3 WTA events in 2021).
    It counts as the deciding set, **not** as a tie-break.
  - `13-12(3)` (Wimbledon 2019, tie-break at 12-12) is a tie-break.
  - **Next Gen Finals** (92 ATP matches: sets to 4 games, no-ad) are **skipped** and counted as skipped, because their
    tie-breaks and deciding sets are not comparable.
- **Deciding set:** a completed match that went the full distance (3rd set of 3, 5th of 5).
- **Completed matches only:** retirements, defaults, abandoned matches and walkovers are skipped, as for serve and return stats.
  An early idea was to drop only the unfinished set; dropping the whole match is simpler and consistent, since the injury
  affects the whole match. Pressure stats do **not** need serve numbers, so they include old Davis Cup matches without stats.

## 13. Return stats come from the opponent's serve numbers
- **Choice:** return points won vs 1st serve = opponent's 1st serves in − 1st serve points they won;
  vs 2nd serve = opponent's 2nd serves − 2nd serve points they won (double faults count as return points won,
  as in official stats); break points converted = opponent's break points faced − saved.
- **Why:** the files have no return columns. Every return point is an opponent's serve point, so this is exact, not an estimate.

## 14. Recent form and team events
- `recent_form` lists the last N matches, newest first (date, then round order). "ret." means the opponent retired,
  "retired" means this player retired. Walkovers are listed but not counted in the win/loss record.
  It reports "retired in X of the last N matches", because repeated retirements can point to injury problems.
- **Team events** (Laver Cup, ATP Cup, United Cup, 473 matches) were filed under ordinary level codes ("ATP 500/250",
  "WTA 250"). They are now labelled "Team event" by tournament name, so a recent-form list never shows the Laver Cup as an ATP 250.

## 15. The scouting report is an MCP prompt, not code
- **Choice:** `scout_report` is an MCP prompt: a fixed set of instructions telling Claude which tools to call and how to write
  the 8 sections. It appears in Claude Code as `/mcp__tennis-scout__scout_report`.
- **Alternatives:** generate the report text in Python.
- **Why:** writing clear takeaways is what the language model is good at; computing numbers is not. So the numbers come from
  tools, and the prompt sets strict rules: copy numbers only from tool answers, cite numbers and match counts for every
  takeaway, flag samples under 10 matches, and never compute new numbers (no differences or averages of its own).
- **Known limit:** these are rules given to the model, not guarantees. The README sample report was checked against the tool answers.
- **What testing showed:** in a first free-form answer (Alcaraz vs Sinner on clay), all 22 numbers in the table matched
  the tools exactly, but the text had two errors where the model reasoned on its own: it counted "3 of 5" matches with a
  tie-break (the real count is 4), and claimed Sinner "avoided tie-breaks" in Monte Carlo 2026 (that match had one).
  So the rules now also forbid counting items in a list yourself and describing play that no number shows, and they ask
  the model to check every takeaway against the scores before writing.
- **Second round:** with `scout_report`, about 60 numbers were again all correct, but (1) the model read a tie-break
  backwards from a score written on the winner's side (`6-7(5)` at Umag 2022, a tie-break Alcaraz won), and (2) the takeaways
  were written for the wrong camp, because my prompt wording ("a report on Alcaraz for a match against Sinner") was ambiguous.
- **Lesson and fix:** a rule is not enough when the model *has* to interpret raw data. So the decoding moved into the tools:
  `head_to_head` and `recent_form` now give tie-breaks won per player, "went to a deciding set", and summary counts
  (for example "matches with a tie-break"). The prompt now says plainly who the coach's player is, fetches that player's
  own serve and return numbers, and forbids decoding score strings.
- **Third round:** the next report had correct facts but ignored the format and chose its own camp ("Alcaraz was named
  first"). It came from a free question, which never sees the prompt. **Fix:** the report rules are now one shared text
  (`REPORT_RULES`), included both in the server instructions (read for *every* question) and in the `scout_report` prompt.
  When it is unclear which player is the coach's, Claude must ask.
- **Fourth round (both ways in, about 120 numbers checked):** the slash-command report had no error. The free-question
  report had all numbers right but two slips: "the only part of his game labelled average" (three serve stats were
  average), and "4 of the 6 tie-breaks", a total it added up itself. **Fix, again in the tools:** `labels_summary`
  groups each answer's stats by label, so "only / all / none" claims can be copied rather than scanned for, and
  `head_to_head` gives `tiebreaks_played`. A vague request ("Alcaraz vs Sinner on clay") correctly made Claude ask
  which player was the coach's.

## 16. Strengths and weaknesses: percentile against the tour, labelled in code
- **Choice:** every serve, return and pressure stat comes with `compared_to_tour`: the tour average, the **percentile**
  (share of other players with a worse value) and a **label** set in code: strength (≥ 75th percentile),
  weakness (≤ 25th), average (in between), "not enough data", or "not enough peers".
- **Peer group:** players on the same tour, with the **same filters** (surface, period), with at least **10 matches**
  behind the stat (10 tie-breaks or deciding sets for pressure stats). The scouted player is not counted.
- **Minimum of 30 peers:** every comparison shows `peers`. Below 30, there is no percentile and the label is
  "not enough peers". With narrow filters (for example grass over a few months), a percentile among a handful of players
  would look precise but mean little.
- **Alternatives:** a fixed gap ("3 points above the tour average"); letting the model judge.
- **Why:** each stat has its own natural spread (1st-serve in % varies a lot between players, 2nd-serve won % much less),
  so one fixed gap would be too strict for some stats and too loose for others. A percentile behaves the same way for every
  stat and is easy to explain ("better than 85% of players"). Letting the model judge is exactly what the project forbids.
- **One formula, three uses:** the same SQL and the same Python formula compute the player, every peer and the tour
  average, so they can never be calculated differently. Test: tour 1st-serve points won + tour return points won vs
  1st serve = 100%, because every serve point is someone's return point.
- **No tour average for pressure stats:** every tie-break has one winner and one loser, so it is always 50%.
  The percentile is still meaningful.
- **Break points saved %** was added to serve stats, as the natural pair of break points converted in the `matchup` tool.
- **`matchup` tool:** places one player's serve next to the other's return (1st serve, 2nd serve, break points), with
  values, match counts, percentiles and labels copied from the serve and return stats. It computes no difference or "edge":
  the model cites the pairs, it does not build them.
- **Limit:** the peer group is every tour-level player with enough matches, not only the top 50, so top players naturally
  rank high. A top-N peer group could come later.

## 17. Default report period: the last 24 months of data
- **Choice:** unless the user asks otherwise, reports use the last 24 months of data, computed from the database
  (`default_report_period()`): **June 2024 – May 2026**. Every report states its period.
- **Alternatives:** the whole history since 2015; the last 12 months.
- **Why:** a player changes over the years, so 2016 numbers say little about the player a coach faces now. 12 months is
  often too few matches on one surface (a clay season is only a few months). 24 months covers two full seasons on every surface.
- **Exceptions:** head-to-head keeps all meetings since 2015 (there are few, and old meetings are still useful context).
  Recent form stays "last 10 matches".

## 11. Ideas for V2 (not now)
- **Coach-focused scouting:** tour averages for the same surface and period next to every stat; a coded strength/weakness
  rule (clearly above or below average **and** at least N matches, otherwise "not enough data"); a matchup view "for my player"
  (opponent's serve vs my player's return, and the other way round); tactical ideas labelled as suggestions, each tied to a cited number.
- **Fresher ATP data:** the TML database has more recent ATP matches. To check: its licence, its columns, and how to merge its player ids.
- **Match Charting Project:** unforced errors and winners, always shown with how many matches are charted.
- **Exact match dates:** Sackmann only gives tournament start dates, so answers say "week of ...".
  Exact days would need a second source (e.g. tennis-data.co.uk) and name matching across sources.
  Guessing the day from the round was rejected: it would be invented data. Order is still correct (round order).
