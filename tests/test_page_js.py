"""Runs the page's JavaScript tests (tests/js/) with Node, so `uv run pytest` covers them too.

Skipped when Node is not installed: the Python tests do not depend on it.
"""

import shutil
import subprocess

import pytest

from tennis_scout.db import PROJECT_ROOT


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
def test_page_reads_every_kind_of_answer():
    run = subprocess.run(["node", "--test", "tests/js/"], cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
