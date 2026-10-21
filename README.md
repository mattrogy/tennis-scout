# tennis-scout

A scouting assistant for tennis coaches and analysts preparing a match against an ATP or WTA player.
Ask "scout Player X for my player on clay" and get a report built **only** from numbers in a database,
each with the number of matches it is based on. The AI never invents or computes statistics itself.

> Work in progress (Day 1 of 3). A full README with setup and a demo comes on Day 2.

**Data through May 2026.** Rankings are as of 8 June 2026.

## Data credit and licence

- **Author of the data:** [Jeff Sackmann](https://www.tennisabstract.com/), originally published in the
  `tennis_atp` and `tennis_wta` GitHub repositories (no longer online).
- **Where the files come from:** the archival mirror
  [Aneeshers/tennis-sackmann-archive](https://github.com/Aneeshers/tennis-sackmann-archive),
  pinned to commit `83733587353df8a41f2fd4f516147d5aa83f5a8d` (June 2026 snapshot).
- **Licence:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/):
  credit the author, non-commercial use only, share derived data under the same licence.

The raw data is **not** stored in this repository. `scripts/download_data.py` downloads it.
