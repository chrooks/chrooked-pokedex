"""AC5 integration: a real apply against Polished Crystal still assembles.

Skipped unless POLISHEDCRYSTAL_DIR points at a real checkout. The checkout is
copied to a scratch dir, the full Ruleset is applied through route_apply
(exactly what the CLI runs), and — when the rgbds toolchain is installed —
`make` must exit 0. Without rgbds the apply-and-report half still runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.dispatch import route_apply
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.report import ApplyReport

_ENV = "POLISHEDCRYSTAL_DIR"
_RULESET = Path(__file__).parent.parent / "ruleset"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def scratch_target(tmp_path_factory):
    src = os.environ.get(_ENV)
    if not src or not Path(src).is_dir():
        pytest.skip(f"{_ENV} not set or not a directory")
    dest = tmp_path_factory.mktemp("pc") / "polishedcrystal"
    shutil.copytree(
        src, dest,
        ignore=shutil.ignore_patterns(".git", "*.o", "*.gbc", "crystal-obj"),
    )
    return dest


def test_full_apply_reports_everything_and_writes(scratch_target):
    ruleset = Ruleset.load(_RULESET)
    report = ApplyReport()
    route_apply(scratch_target, "polishedcrystal", ruleset, report)

    # Nothing silently dropped: every species with a learnset/abilities override
    # and every move/ability def produced a report entry.
    assert report.entries
    counts = report.counts()
    assert counts["applied"] + counts["partial"] + counts["blocked"] == len(report.entries)


def test_rom_still_assembles_after_apply(scratch_target):
    if shutil.which("rgbasm") is None:
        pytest.skip("rgbds toolchain not installed")
    ruleset = Ruleset.load(_RULESET)
    report = ApplyReport()
    route_apply(scratch_target, "polishedcrystal", ruleset, report)
    result = subprocess.run(
        ["make", "-j4"], cwd=scratch_target, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
