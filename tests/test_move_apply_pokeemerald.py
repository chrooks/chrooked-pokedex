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
        .makesContact = TRUE,
    },
"""


def _entry(target: Path, symbol: str) -> str:
    from chrooked_pokedex.appliers.pokeemerald import c_edit
    text = _moves_text(target)
    span = c_edit.find_entry(text, symbol)
    return text[span[0]:span[1]]


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


def test_effect_overlay_lands(tmp_path):
    target = _target(tmp_path)
    tackle = MoveDef(name="Tackle", chrooked_id="tackle", type="Normal",
                     category="physical", power=40, accuracy=100, pp=35,
                     effect="multi_hit", flags=("contact",),
                     aka={"pokeemerald": "MOVE_TACKLE"})
    ruleset = Ruleset(moves={"tackle": tackle})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    assert ".effect = EFFECT_MULTI_HIT," in _entry(target, "MOVE_TACKLE")
    assert "effect" in report.entries[0].reason


def test_flag_add_keeps_existing_and_adds_new(tmp_path):
    target = _target(tmp_path)
    # Tackle already makesContact; add biting, keep contact.
    tackle = MoveDef(name="Tackle", chrooked_id="tackle", type="Normal",
                     category="physical", power=40, accuracy=100, pp=35,
                     flags=("contact", "biting"), aka={"pokeemerald": "MOVE_TACKLE"})
    ruleset = Ruleset(moves={"tackle": tackle})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    entry = _entry(target, "MOVE_TACKLE")
    assert ".bitingMove = TRUE," in entry      # added
    assert ".makesContact = TRUE," in entry    # preserved


def test_flag_remove_when_ruleset_drops_it(tmp_path):
    target = _target(tmp_path)
    # Ruleset Tackle sets no flags -> the modeled makesContact flag is removed.
    tackle = MoveDef(name="Tackle", chrooked_id="tackle", type="Normal",
                     category="physical", power=40, accuracy=100, pp=35, flags=(),
                     aka={"pokeemerald": "MOVE_TACKLE"})
    ruleset = Ruleset(moves={"tackle": tackle})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    entry = _entry(target, "MOVE_TACKLE")
    assert ".makesContact" not in entry
    assert any("-makesContact" in f for f in [report.entries[0].reason])


def test_additional_effects_overlay(tmp_path):
    target = _target(tmp_path)
    from chrooked_pokedex.model.schema import AdditionalEffect
    tackle = MoveDef(name="Tackle", chrooked_id="tackle", type="Normal",
                     category="physical", power=40, accuracy=100, pp=35,
                     flags=("contact",),
                     additional_effects=(AdditionalEffect(effect="burn", chance=10),),
                     aka={"pokeemerald": "MOVE_TACKLE"})
    ruleset = Ruleset(moves={"tackle": tackle})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    entry = _entry(target, "MOVE_TACKLE")
    assert ".additionalEffects = ADDITIONAL_EFFECTS(" in entry
    assert ".moveEffect = MOVE_EFFECT_BURN, .chance = 10" in entry


def test_stale_additional_effects_reported_not_silently_kept(tmp_path):
    # Target Tackle has a secondary; the Ruleset drops it. We can't cleanly clear the
    # macro yet, so it must be REPORTED (partial), never silently left behind.
    moves = (
        "const struct MoveInfo gMovesInfo[] = {\n"
        "    [MOVE_TACKLE] =\n    {\n"
        '        .name = COMPOUND_STRING("Tackle"),\n'
        "        .effect = EFFECT_HIT,\n"
        "        .type = TYPE_NORMAL,\n        .power = 40,\n"
        "        .accuracy = 100,\n        .pp = 35,\n"
        "        .category = DAMAGE_CATEGORY_PHYSICAL,\n"
        "        .additionalEffects = ADDITIONAL_EFFECTS({ .moveEffect = MOVE_EFFECT_POISON, .chance = 30 }),\n"
        "    },\n};\n"
    )
    target = tmp_path / "fork"
    d = target / "src" / "data"
    d.mkdir(parents=True)
    (d / "moves_info.h").write_text(moves, encoding="utf-8")

    tackle = MoveDef(name="Tackle", chrooked_id="tackle", type="Normal",
                     category="physical", power=40, accuracy=100, pp=35,
                     aka={"pokeemerald": "MOVE_TACKLE"})  # no additional_effects
    ruleset = Ruleset(moves={"tackle": tackle})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    entry = [e for e in report.entries if e.chrooked_id == "tackle"][0]
    assert entry.status == "partial"
    assert any("additionalEffects" in f for f in entry.partial_fields)
    # and it is genuinely still in the file (not silently dropped, not corrupted)
    assert "MOVE_EFFECT_POISON" in _moves_text(target)


def test_argument_overlay(tmp_path):
    target = _target(tmp_path)
    tackle = MoveDef(name="Tackle", chrooked_id="tackle", type="Steel",
                     category="physical", power=40, accuracy=100, pp=35,
                     effect="super_effective_on_arg", argument={"type": "Dragon"},
                     flags=("contact",), aka={"pokeemerald": "MOVE_TACKLE"})
    ruleset = Ruleset(moves={"tackle": tackle})
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_moves(target, ruleset, resmap, report)
    entry = _entry(target, "MOVE_TACKLE")
    assert ".effect = EFFECT_SUPER_EFFECTIVE_ON_ARG," in entry
    assert ".argument = { .type = TYPE_DRAGON }," in entry
