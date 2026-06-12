"""pokeemerald: edit existing owned moves (the silent-drop fix).

Before this tier, an owned move the target already had (a move the fork merely
retuned, e.g. Fly's power) was skipped by creation with no Apply Report line — a
silent drop. This tier overlays the scalar retune fields (type, category, power,
accuracy, pp, priority) onto the existing entry, diff-based: only fields that
actually differ are written, so a move already matching produces no churn.
"""

from pathlib import Path

from chrooked_pokedex.appliers.pokeemerald.move_apply import apply_moves
from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import MoveDef
from chrooked_pokedex.report import ApplyReport

_MOVES = """\
    [MOVE_FLY] =
    {
        .name = COMPOUND_STRING("Fly"),
        .effect = EFFECT_SEMI_INVULNERABLE,
        .type = TYPE_FLYING,
        .power = 90,
        .accuracy = 95,
        .pp = 15,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
    [MOVE_TACKLE] =
    {
        .name = COMPOUND_STRING("Tackle"),
        .effect = EFFECT_HIT,
        .type = TYPE_NORMAL,
        .power = 40,
        .accuracy = 100,
        .pp = 35,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
"""


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "fork"
    d = target / "src" / "data"
    d.mkdir(parents=True)
    (d / "moves_info.h").write_text(f"const struct MoveInfo gMovesInfo[] = {{\n{_MOVES}}};\n", encoding="utf-8")
    return target


def _moves_text(target: Path) -> str:
    return (target / "src" / "data" / "moves_info.h").read_text(encoding="utf-8")


def test_retuned_power_lands_and_is_reported(tmp_path):
    target = _target(tmp_path)
    fly = MoveDef(name="Fly", chrooked_id="fly", type="Flying", category="physical",
                  power=95, accuracy=95, pp=15, effect="semi_invulnerable",
                  aka={"pokeemerald": "MOVE_FLY"})
    ruleset = Ruleset(moves={"fly": fly})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_moves(target, ruleset, resmap, report)

    assert (target / "src" / "data" / "moves_info.h") in changed
    text = _moves_text(target)
    assert ".power = 95," in text  # retune landed
    assert ".power = 40," in text  # Tackle untouched
    entry = [e for e in report.entries if e.chrooked_id == "fly"][0]
    assert entry.status == "applied"
    assert "power" in entry.reason


def test_unchanged_move_produces_no_entry_no_churn(tmp_path):
    target = _target(tmp_path)
    before = _moves_text(target)
    # Fly defined identically to the target -> nothing to write.
    fly = MoveDef(name="Fly", chrooked_id="fly", type="Flying", category="physical",
                  power=90, accuracy=95, pp=15, effect="semi_invulnerable",
                  aka={"pokeemerald": "MOVE_FLY"})
    ruleset = Ruleset(moves={"fly": fly})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_moves(target, ruleset, resmap, report)
    assert changed == set()
    assert _moves_text(target) == before
    assert report.entries == []


def test_move_missing_from_target_is_skipped_not_blocked(tmp_path):
    # A move the target lacks is creation's job, not this tier's — no entry here.
    target = _target(tmp_path)
    exc = MoveDef(name="Excalibur", chrooked_id="excalibur", type="Steel",
                  category="physical", power=120, aka={"pokeemerald": "MOVE_EXCALIBUR"})
    ruleset = Ruleset(moves={"excalibur": exc})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    assert report.entries == []


def test_type_and_category_retune_lands(tmp_path):
    target = _target(tmp_path)
    tackle = MoveDef(name="Tackle", chrooked_id="tackle", type="Fighting",
                     category="special", power=40, accuracy=100, pp=35, effect="hit",
                     aka={"pokeemerald": "MOVE_TACKLE"})
    ruleset = Ruleset(moves={"tackle": tackle})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    text = _moves_text(target)
    assert ".type = TYPE_FIGHTING," in text
    assert ".category = DAMAGE_CATEGORY_SPECIAL," in text


def test_behavior_fields_noted_when_present(tmp_path):
    # A retuned move that also carries a non-hit effect is reported, with a note that
    # behavior fields are not overlaid by this scalar tier (visible, not silent).
    target = _target(tmp_path)
    fly = MoveDef(name="Fly", chrooked_id="fly", type="Flying", category="physical",
                  power=100, accuracy=95, pp=15, effect="semi_invulnerable",
                  aka={"pokeemerald": "MOVE_FLY"})
    ruleset = Ruleset(moves={"fly": fly})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    entry = [e for e in report.entries if e.chrooked_id == "fly"][0]
    assert "behavior" in entry.reason.lower()
