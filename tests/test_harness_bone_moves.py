"""Rejuv's Bone Breaker list covers every bone-flagged move in the Ruleset.

Rejuv has no bone flag, so `chrooked_bonebreaker.rb` keys bone moves by symbol.
Bone Torch and Bone Chill joined the Ruleset with `flags: [bone]` after the list
was written, and neither got the +20% or the immunity bypass in game (found on
the Aevian Golisopod design, 2026-10-07).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).parent.parent
_HARNESS = _ROOT / "references" / "rejuv-harness" / "chrooked_bonebreaker.rb"
_MOVES = _ROOT / "ruleset" / "moves"


def test_bonebreaker_list_names_every_bone_flagged_move():
    listed = set(re.findall(
        r":(\w+)", re.search(r"BONEBREAKER_BONE_MOVES = \[(.*?)\]", _HARNESS.read_text()).group(1)
    ))
    flagged = {
        re.sub(r"[^A-Z0-9]", "", move["name"].upper())
        for path in _MOVES.glob("*.yaml")
        if "bone" in ((move := yaml.safe_load(path.read_text())) or {}).get("flags", [])
    }
    assert flagged, "no bone-flagged moves found — the scan itself broke"
    assert flagged <= listed, f"missing from the Rejuv list: {sorted(flagged - listed)}"
