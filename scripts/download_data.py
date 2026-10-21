"""Download the raw tennis CSV files into data/raw/.

The data was compiled by Jeff Sackmann (CC BY-NC-SA 4.0). His original repositories are
no longer online, so we download from an archival mirror, pinned to one fixed commit so that
everyone gets exactly the same files.

Usage:
    uv run python scripts/download_data.py           # skip files already downloaded
    uv run python scripts/download_data.py --force   # download everything again
"""

import argparse
import urllib.request
from pathlib import Path

MIRROR_REPO = "Aneeshers/tennis-sackmann-archive"
MIRROR_COMMIT = "83733587353df8a41f2fd4f516147d5aa83f5a8d"
BASE_URL = f"https://raw.githubusercontent.com/{MIRROR_REPO}/{MIRROR_COMMIT}"

TOURS = ["atp", "wta"]
FIRST_YEAR = 2015
LAST_YEAR = 2026

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def files_to_download():
    """List the files we need: tour-level matches per year, players, current rankings."""
    names = []
    for tour in TOURS:
        for year in range(FIRST_YEAR, LAST_YEAR + 1):
            names.append(f"{tour}/{tour}_matches_{year}.csv")
        names.append(f"{tour}/{tour}_players.csv")
        names.append(f"{tour}/{tour}_rankings_current.csv")
    return names


def download(remote_path, force):
    """Download one file, unless it is already on disk (and --force was not given)."""
    target = RAW_DIR / Path(remote_path).name
    if target.exists() and not force:
        print(f"  skip  {target.name} (already downloaded)")
        return
    url = f"{BASE_URL}/{remote_path}"
    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read()
    target.write_bytes(content)
    print(f"  saved {target.name} ({len(content) // 1024} KB)")


def main():
    parser = argparse.ArgumentParser(description="Download Sackmann tennis data from the pinned mirror.")
    parser.add_argument("--force", action="store_true", help="download again even if files exist")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Source: {MIRROR_REPO} @ {MIRROR_COMMIT[:7]}")
    print(f"Target: {RAW_DIR}")
    for remote_path in files_to_download():
        download(remote_path, args.force)
    print("Done. Data by Jeff Sackmann, licensed CC BY-NC-SA 4.0.")


if __name__ == "__main__":
    main()
