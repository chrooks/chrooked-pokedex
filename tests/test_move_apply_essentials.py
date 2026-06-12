"""Essentials: edit existing owned moves in PBS (the silent-drop fix, PBS side).

Mirrors the pokeemerald move tier: overlay scalar retune fields (Type, Category,
Power, Accuracy, TotalPP, Priority) onto an existing `[INTERNAL]` move section,
diff-based, so only genuine retunes are written and reported.
"""

from pathlib import Path

from chrooked_pokedex.appliers.essentials import pbs_edit
from chrooked_pokedex.appliers.essentials.move_apply import apply_moves
from chrooked_pokedex.appliers.essentials.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import MoveDef
from chrooked_pokedex.report import ApplyReport

_MOVES = """\
[FLY]
Name = Fly
Type = FLYING
Category = Physical
Power = 90
Accuracy = 95
TotalPP = 15
FunctionCode = TwoTurnAttackInvulnerableInSky

[TACKLE]
Name = Tackle
Type = NORMAL
Category = Physical
Power = 40
Accuracy = 100
TotalPP = 35
"""

_TYPES = "[FLYING]\nName = Flying\n[NORMAL]\nName = Normal\n[FIGHTING]\nName = Fighting\n"


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "essentials"
    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    (pbs / "moves.txt").write_text(_MOVES, encoding="utf-8")
    (pbs / "types.txt").write_text(_TYPES, encoding="utf-8")
    return target


def _field(target: Path, header: str, key: str) -> str | None:
    text = (target / "PBS" / "moves.txt").read_text(encoding="utf-8")
    span = pbs_edit.find_section(text, header)
    return pbs_edit.get_field(text[span[0]:span[1]], key) if span else None


def test_retuned_power_lands_and_reported(tmp_path):
    target = _target(tmp_path)
    fly = MoveDef(name="Fly", chrooked_id="fly", type="Flying", category="physical",
                  power=95, accuracy=95, pp=15, effect="semi_invulnerable",
                  aka={"essentials": "FLY"})
    ruleset = Ruleset(moves={"fly": fly})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_moves(target, ruleset, resmap, report)
    assert (target / "PBS" / "moves.txt") in changed
    assert _field(target, "FLY", "Power") == "95"
    assert _field(target, "TACKLE", "Power") == "40"  # untouched
    entry = [e for e in report.entries if e.chrooked_id == "fly"][0]
    assert entry.status == "applied"
    assert "Power" in entry.reason


def test_unchanged_move_no_entry_no_churn(tmp_path):
    target = _target(tmp_path)
    before = (target / "PBS" / "moves.txt").read_text(encoding="utf-8")
    fly = MoveDef(name="Fly", chrooked_id="fly", type="Flying", category="physical",
                  power=90, accuracy=95, pp=15, aka={"essentials": "FLY"})
    ruleset = Ruleset(moves={"fly": fly})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_moves(target, ruleset, resmap, report)
    assert changed == set()
    assert (target / "PBS" / "moves.txt").read_text(encoding="utf-8") == before
    assert report.entries == []


def test_missing_move_skipped(tmp_path):
    target = _target(tmp_path)
    exc = MoveDef(name="Excalibur", chrooked_id="excalibur", type="Steel",
                  category="physical", power=120, aka={"essentials": "EXCALIBUR"})
    ruleset = Ruleset(moves={"excalibur": exc})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    assert report.entries == []


def test_type_and_category_retune_lands(tmp_path):
    target = _target(tmp_path)
    tackle = MoveDef(name="Tackle", chrooked_id="tackle", type="Fighting",
                     category="special", power=40, accuracy=100, pp=35,
                     aka={"essentials": "TACKLE"})
    ruleset = Ruleset(moves={"tackle": tackle})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    assert _field(target, "TACKLE", "Type") == "FIGHTING"
    assert _field(target, "TACKLE", "Category") == "Special"


def test_unresolvable_type_reported_partial(tmp_path):
    target = _target(tmp_path)  # types.txt lacks Cosmic
    fly = MoveDef(name="Fly", chrooked_id="fly", type="Cosmic", category="physical",
                  power=90, accuracy=95, pp=15, aka={"essentials": "FLY"})
    ruleset = Ruleset(moves={"fly": fly})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    entry = [e for e in report.entries if e.chrooked_id == "fly"][0]
    assert entry.status == "partial"
    assert any("type:Cosmic" in f for f in entry.partial_fields)
    assert _field(target, "FLY", "Type") == "FLYING"  # not overwritten with a bad value
