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

## Open point for Day 2
- **Next Gen Finals** (62 + 30 ATP matches) use special rules: sets to 4 games and no-ad scoring.
  They are labelled separately ("Next Gen Finals") so the tie-break and deciding-set stats can decide whether to leave them out.
- **Retirement frequency as a scouting signal:** `recent_form` could show "retired in X of the last N matches"
  (a count from the database), since repeated retirements can point to injury problems.

## 11. Ideas for V2 (not now)
- **Fresher ATP data:** the TML database has more recent ATP matches. To check: its licence, its columns, and how to merge its player ids.
- **Match Charting Project:** unforced errors and winners, always shown with how many matches are charted.
- **Exact match dates:** Sackmann only gives tournament start dates, so answers say "week of ...".
  Exact days would need a second source (e.g. tennis-data.co.uk) and name matching across sources.
  Guessing the day from the round was rejected: it would be invented data. Order is still correct (round order).
