"""Unit tests for the learnset-ladder auditor/fixer (scripts/learnset_ladder.py).

Guards the one transform left after the dedup retirement (2026-08-26):
reorder rungs into ascending band order, deleting nothing.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# scripts/ is not a package; load the module by path (mirrors test_move_coverage).
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "learnset_ladder.py"
_spec = importlib.util.spec_from_file_location("learnset_ladder", _SCRIPT)
assert _spec and _spec.loader
ll = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ll)


@pytest.fixture(scope="module")
def ctx() -> "ll.Ctx":
    return ll.Ctx()


@pytest.mark.unit
def test_reorder_puts_lower_band_first(ctx) -> None:
    """A net-new 91-110 rung learned before a 76-90 rung is swapped by level."""
    rows = [
        (38, "Interment"),    # Ghost phys 91-110, net-new
        (43, "Wraithstrike"),  # Ghost phys 76-90, net-new
        (49, "Necrosis"),      # Ghost phys >110, net-new
    ]
    out = ll.transform(rows, ctx)
    assert out == [(38, "Wraithstrike"), (43, "Interment"), (49, "Necrosis")]


@pytest.mark.unit
def test_shared_cell_rungs_are_kept_and_reordered(ctx) -> None:
    """Dedup is retired: a same-cell custom rung survives; only order changes."""
    rows = [
        (38, "Nosedive"),    # Flying phys 91-109, net-new
        (41, "Drill Peck"),  # Flying phys 76-90, canon
        (48, "Dive Bomb"),   # Flying phys 76-90, net-new — kept, never dropped
    ]
    out = ll.transform(rows, ctx)
    moves = [mv for _, mv in out]
    assert moves.count("Dive Bomb") == 1  # nothing deleted
    # rungs ascend by band: both 76-90 rungs before Nosedive(91-109)
    assert out == [(38, "Drill Peck"), (41, "Dive Bomb"), (48, "Nosedive")]


@pytest.mark.unit
def test_anchors_and_non_ladder_moves_untouched(ctx) -> None:
    """L0/L1 kit and status moves keep their levels; already-sorted = no change."""
    rows = [
        (0, "High Horsepower"),  # anchor
        (1, "Pound"),            # anchor, sub-ladder
        (28, "Curse"),           # status, non-ladder
        (38, "Wraithstrike"),    # 76-90
        (43, "Interment"),       # 91-110
    ]
    assert ll.transform(rows, ctx) is None  # already ascending -> unchanged
