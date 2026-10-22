"""Pre-launch check of the writer model: write real reports and run the automatic checks on them.

Uses the real database and your OpenRouter key from .env (never printed). Each report and the tool
answers it was written from are saved in checks/ (git-ignored), for the manual read.

Usage:
    uv run python scripts/check_reports.py                    # all cases, with the website's model (llm.MODEL)
    uv run python scripts/check_reports.py 2 5                # only cases 2 and 5
    uv run python scripts/check_reports.py --model anthropic/claude-haiku-5.5   # try another model (testing only)
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tennis_scout import llm
from tennis_scout.report import build_messages, check_report, gather_report_data

CHECKS_DIR = Path(__file__).resolve().parent.parent / "checks"

# (scouted player, coach's player or None, surface or None, what the case tests)
CASES = [
    ("atp-207989", "atp-206173", "Clay", "ATP, coach's player, surface (Alcaraz scouted for Sinner)"),
    ("atp-104925", None, None, "ATP, no coach's player, all surfaces (Djokovic)"),
    ("wta-214544", "wta-216347", "Hard", "WTA, coach's player, surface (Sabalenka scouted for Swiatek)"),
    ("wta-221103", None, "Clay", "WTA, no coach's player, surface (Gauff)"),
    ("atp-208029", "atp-210097", "Grass", "small sample: Rune has 9 grass matches (scouted for Shelton)"),
    ("wta-259799", "wta-202468", None, "no head-to-head (Andreeva scouted for Pegula)"),
]


BUSY_ATTEMPTS = 3      # this script only: the website never waits and retries
BUSY_WAIT_SECONDS = 30


def write_with_patience(messages, model):
    """Ask for a report; if the model is busy, wait and try again a few times."""
    for attempt in range(1, BUSY_ATTEMPTS + 1):
        try:
            return llm.write_report(messages, model=model)
        except llm.ModelBusy:
            if attempt == BUSY_ATTEMPTS:
                raise
            print(f"  (a case waits {BUSY_WAIT_SECONDS} s: model busy, attempt {attempt} of {BUSY_ATTEMPTS})")
            time.sleep(BUSY_WAIT_SECONDS)


def run_case(model, out_dir, number, scouted, coach, surface, about):
    """Write and check one report. Returns (passed, the lines to print)."""
    lines = [f"\nCase {number}: {about}"]
    data = gather_report_data(scouted, coach=coach, surface=surface)
    started = time.perf_counter()
    try:
        reply = write_with_patience(build_messages(data), model)
    except Exception as error:  # testing script only: one failed case must not hide the other cases' results
        return False, lines + [f"  not written: {type(error).__name__}: {error}"]
    seconds = time.perf_counter() - started
    check = check_report(reply["text"], data)

    (out_dir / f"{number}.md").write_text(reply["text"], encoding="utf-8")
    (out_dir / f"{number}-tool-answers.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                                         encoding="utf-8")
    return check["passed"], lines + [
        f"  passed: {check['passed']}",
        f"  numbers not found: {check['numbers_not_found'] or 'none'}",
        f"  problems: {check['problems'] or 'none'}",
        f"  model: {reply['model']}, finish: {reply['finish_reason']}, {seconds:.0f} s, "
        f"tokens in/out: {reply['input_tokens']}/{reply['output_tokens']} "
        f"(of which reasoning: {reply['reasoning_tokens']})",
    ]


def main():
    parser = argparse.ArgumentParser(description="Write real reports and check them.")
    parser.add_argument("cases", nargs="*", type=int, help="case numbers (default: all)")
    parser.add_argument("--model", default=llm.MODEL, help=f"OpenRouter model ID (default: {llm.MODEL})")
    args = parser.parse_args()

    # One folder per model, so a comparison never overwrites the other model's reports.
    out_dir = CHECKS_DIR / args.model.replace("/", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    numbers = args.cases or range(1, len(CASES) + 1)
    print(f"Writer model: {args.model}. Writing {len(numbers)} reports at the same time...")
    # All cases at once: the run takes about as long as the slowest report, not the sum of all of them.
    with ThreadPoolExecutor(max_workers=len(numbers)) as pool:
        results = list(pool.map(lambda number: run_case(args.model, out_dir, number, *CASES[number - 1]), numbers))
    for _, lines in results:
        print("\n".join(lines))
    passed = sum(1 for ok, _ in results if ok)
    print(f"\n{passed} of {len(results)} reports passed the automatic checks. Reports saved in {out_dir}/")


if __name__ == "__main__":
    main()
