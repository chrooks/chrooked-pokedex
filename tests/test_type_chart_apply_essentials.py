"""Essentials: type-chart Overrides edit `types.txt` Weaknesses/Resistances/Immunities.

pokeemerald stores effectiveness as a numeric matrix; Essentials stores it per type
as three buckets on the DEFENDER — `Weaknesses` (2x), `Resistances` (0.5x),
`Immunities` (0x) — each a comma-list of attacking type internals. So an
attacker->defender Override edits the *defender's* section: the attacker is added to
the matching bucket and removed from the other two. A multiplier Essentials cannot
express (anything but 2, 0.5, 0, or 1) is reported, never forced into the nearest bucket.
"""

from pathlib import Path

from chrooked_pokedex.appliers.essentials import pbs_edit
from chrooked_pokedex.appliers.essentials.resolution import build_resolution_map
from chrooked_pokedex.appliers.essentials.type_chart_apply import apply_type_chart
from chrooked_pokedex.model import Ruleset

from chrooked_pokedex.report import ApplyReport

_TYPES = """\
[NORMAL]
Name = Normal
Weaknesses = FIGHTING
Immunities = GHOST

[FIRE]
Name = Fire
Weaknesses = GROUND,ROCK,WATER
Resistances = BUG,STEEL,FIRE,GRASS,ICE,FAIRY

[ICE]
Name = Ice
Weaknesses = FIRE,FIGHTING,ROCK,STEEL
Resistances = ICE

[DRAGON]
Name = Dragon
Weaknesses = ICE,DRAGON,FAIRY
Resistances = FIRE,WATER,GRASS,ELECTRIC
"""


def _target(tmp_path: Path, body: str = _TYPES) -> Path:
    target = tmp_path / "essentials"
    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    (pbs / "types.txt").write_text(body, encoding="utf-8")
    return target


def _ruleset(tmp_path: Path, overrides_yaml: str) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "type-chart").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "type-chart" / "overrides.yaml").write_text(overrides_yaml, encoding="utf-8")
    return Ruleset.load(root)


def _bucket(target: Path, header: str, key: str) -> list[str]:
    text = (target / "PBS" / "types.txt").read_text(encoding="utf-8")
    span = pbs_edit.find_section(text, header)
    raw = pbs_edit.get_field(text[span[0]:span[1]], key)
    return raw.split(",") if raw else []


def test_weakness_adds_attacker_to_defender(tmp_path):
    # Fire -> Dragon becomes super-effective (2x): FIRE joins Dragon's Weaknesses.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Fire, defender: Dragon, multiplier: 2.0 }\n")
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_type_chart(target, ruleset, resmap, report)
    assert changed
    assert "FIRE" in _bucket(target, "DRAGON", "Weaknesses")
    # and it leaves Dragon's old Resistances entry for FIRE gone (no contradiction).
    assert "FIRE" not in _bucket(target, "DRAGON", "Resistances")
    assert report.counts()["applied"] == 1


def test_resistance_moves_attacker_between_buckets(tmp_path):
    # Ice -> Dragon set to 0.5x: ICE leaves Weaknesses, joins Resistances.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Ice, defender: Dragon, multiplier: 0.5 }\n")
    resmap = build_resolution_map(target, ruleset)
    apply_type_chart(target, ruleset, resmap, ApplyReport())
    assert "ICE" not in _bucket(target, "DRAGON", "Weaknesses")
    assert "ICE" in _bucket(target, "DRAGON", "Resistances")


def test_immunity_adds_to_immunities(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Fire, defender: Dragon, multiplier: 0.0 }\n")
    resmap = build_resolution_map(target, ruleset)
    apply_type_chart(target, ruleset, resmap, ApplyReport())
    assert "FIRE" in _bucket(target, "DRAGON", "Immunities")


def test_neutral_removes_attacker_from_all_buckets(tmp_path):
    # Ice -> Dragon set back to neutral (1.0): ICE drops out of Weaknesses entirely.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Ice, defender: Dragon, multiplier: 1.0 }\n")
    resmap = build_resolution_map(target, ruleset)
    apply_type_chart(target, ruleset, resmap, ApplyReport())
    assert "ICE" not in _bucket(target, "DRAGON", "Weaknesses")
    assert "ICE" not in _bucket(target, "DRAGON", "Resistances")
    assert "ICE" not in _bucket(target, "DRAGON", "Immunities")


def test_idempotent_no_second_change(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Fire, defender: Dragon, multiplier: 2.0 }\n")
    resmap = build_resolution_map(target, ruleset)
    apply_type_chart(target, ruleset, resmap, ApplyReport())
    first = (target / "PBS" / "types.txt").read_text(encoding="utf-8")
    second_report = ApplyReport()
    changed = apply_type_chart(target, ruleset, resmap, second_report)
    second = (target / "PBS" / "types.txt").read_text(encoding="utf-8")
    assert first == second
    assert changed == set()
    # A no-op second run must add NO report line — "applied" means a real edit.
    assert second_report.entries == []


def test_already_satisfied_override_reports_nothing(tmp_path):
    # Fire is already in Dragon's... no — assert the already-in-bucket case: ICE is
    # already in Dragon's Weaknesses, so a 2.0 Ice->Dragon override is a true no-op.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Ice, defender: Dragon, multiplier: 2.0 }\n")
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = apply_type_chart(target, ruleset, resmap, report)
    assert changed == set()
    assert report.entries == []


def test_unportable_multiplier_blocked_not_forced(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Fire, defender: Dragon, multiplier: 4.0 }\n")
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()
    apply_type_chart(target, ruleset, resmap, report)
    entry = [e for e in report.entries if e.category == "type-chart"][0]
    assert entry.status == "blocked"
    # nothing forced into a bucket
    assert "FIRE" not in _bucket(target, "DRAGON", "Weaknesses")


def test_unknown_type_blocked(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Cosmic, defender: Dragon, multiplier: 2.0 }\n")
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()
    apply_type_chart(target, ruleset, resmap, report)
    entry = [e for e in report.entries if e.category == "type-chart"][0]
    assert entry.status == "blocked"


def test_weakness_into_absent_bucket_inserts_line(tmp_path):
    # Normal has no Resistances line; a 0.5x override must insert one cleanly.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, "overrides:\n  - { attacker: Fire, defender: Normal, multiplier: 0.5 }\n")
    resmap = build_resolution_map(target, ruleset)
    apply_type_chart(target, ruleset, resmap, ApplyReport())
    assert _bucket(target, "NORMAL", "Resistances") == ["FIRE"]


def test_no_overrides_no_write(tmp_path):
    target = _target(tmp_path)
    before = (target / "PBS" / "types.txt").read_text(encoding="utf-8")
    ruleset = _ruleset(tmp_path, "overrides: []\n")
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = apply_type_chart(target, ruleset, resmap, report)
    assert changed == set()
    assert (target / "PBS" / "types.txt").read_text(encoding="utf-8") == before
