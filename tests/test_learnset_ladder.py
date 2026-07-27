"""Unit tests for the learnset-ladder auditor/fixer (scripts/learnset_ladder.py).

Guards the two transforms the distribution pass needs cleaned up:
reorder net-new rungs into ascending band order, and drop a net-new rung that
duplicates a canon move's (type, split, band) cell.
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
def test_dedup_drops_net_new_when_canon_shares_cell(ctx) -> None:
    """Dive Bomb (net-new 76-90) is dropped; canon Drill Peck (76-90) stays."""
    rows = [
        (38, "Nosedive"),    # Flying phys 91-110, net-new
        (41, "Drill Peck"),  # Flying phys 76-90, canon
        (48, "Dive Bomb"),   # Flying phys 76-90, net-new -> dropped
    ]
    out = ll.transform(rows, ctx)
    moves = [mv for _, mv in out]
    assert "Dive Bomb" not in moves
    assert "Drill Peck" in moves
    # kept rungs ascend by band: Drill Peck(76-90) before Nosedive(91-110)
    assert moves.index("Drill Peck") < moves.index("Nosedive")


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
