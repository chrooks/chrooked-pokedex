"""Move behavior data: effect, argument, additional_effects, flags, priority, target.

These are the fields that make a created move actually *do* something. Without them a
created move is inert (right numbers, no burn/flinch, no contact flag). The slice carries
them engine-neutrally end to end: read from the fork, write YAML, load back, render to C.
"""

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.pokeemerald.creation import _move_entry
from chrooked_pokedex.appliers.pokeemerald.resolution import ResolutionMap
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.loader import load_move
from chrooked_pokedex.seed.extractor import seed_from_fork
from chrooked_pokedex.seed.writer import move_yaml


def _write_moves(repo: Path, body: str) -> None:
    d = repo / "src" / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "moves_info.h").write_text(body, encoding="utf-8")


_BASE = """\
    [MOVE_CINDER_SMASH] =
    {
        .name = COMPOUND_STRING("Cinder Smash"),
        .effect = EFFECT_HIT,
        .type = TYPE_FIRE,
        .power = 80,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },
"""

# Fork changes Cinder Smash: power up, makesContact + a burn secondary effect.
_FORK = """\
    [MOVE_CINDER_SMASH] =
    {
        .name = COMPOUND_STRING("Cinder Smash"),
        .effect = EFFECT_HIT,
        .type = TYPE_FIRE,
        .power = 90,
        .category = DAMAGE_CATEGORY_PHYSICAL,
        .makesContact = TRUE,
        .additionalEffects = ADDITIONAL_EFFECTS({
            .moveEffect = MOVE_EFFECT_BURN,
            .chance = 10,
        }),
    },
    [MOVE_EXCALIBUR] =
    {
        .name = COMPOUND_STRING("Excalibur"),
        .effect = EFFECT_SUPER_EFFECTIVE_ON_ARG,
        .type = TYPE_STEEL,
        .power = 120,
        .category = DAMAGE_CATEGORY_PHYSICAL,
        .argument = { .type = TYPE_DRAGON },
        .makesContact = TRUE,
    },
"""


def test_seed_captures_move_behavior_fields(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_moves(base, _BASE)
    _write_moves(fork, _FORK)

    seed = seed_from_fork(fork, base)

    cs = seed.moves["cindersmash"]
    assert cs.flags == ("contact",)
    assert len(cs.additional_effects) == 1
    assert cs.additional_effects[0].effect == "burn"
    assert cs.additional_effects[0].chance == 10

    # Excalibur is NEW (not in base) -> owned, with a parameterized primary effect.
    exc = seed.moves["excalibur"]
    assert exc.effect == "super_effective_on_arg"
    assert exc.argument == {"type": "Dragon"}


def test_move_fields_round_trip_through_yaml(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_moves(base, _BASE)
    _write_moves(fork, _FORK)
    seed = seed_from_fork(fork, base)

    for move in (seed.moves["cindersmash"], seed.moves["excalibur"]):
        path = tmp_path / f"{move.chrooked_id}.yaml"
        path.write_text(move_yaml(move), encoding="utf-8")
        reloaded = load_move(path)
        assert reloaded.effect == move.effect
        assert reloaded.argument == move.argument
        assert reloaded.additional_effects == move.additional_effects
        assert reloaded.flags == move.flags


def test_creation_renders_behavior_fields_to_c(tmp_path: Path) -> None:
    base, fork = tmp_path / "base", tmp_path / "fork"
    _write_moves(base, _BASE)
    _write_moves(fork, _FORK)
    seed = seed_from_fork(fork, base)
    resmap = ResolutionMap()

    cs_c = _move_entry("MOVE_CINDER_SMASH", seed.moves["cindersmash"], resmap)
    # the burn secondary effect and the contact flag land in C
    assert ".additionalEffects = ADDITIONAL_EFFECTS(" in cs_c
    assert ".moveEffect = MOVE_EFFECT_BURN, .chance = 10" in cs_c
    assert ".makesContact = TRUE," in cs_c

    exc_c = _move_entry("MOVE_EXCALIBUR", seed.moves["excalibur"], resmap)
    # parameterized primary effect + its type argument round-trip to C
    assert ".effect = EFFECT_SUPER_EFFECTIVE_ON_ARG," in exc_c
    assert ".argument = { .type = TYPE_DRAGON }," in exc_c


def test_plain_move_renders_defaults_to_c(tmp_path: Path) -> None:
    """A move with no flags/effects still gets explicit .effect/.target and NO
    additionalEffects or flag lines."""
    from chrooked_pokedex.model.schema import MoveDef

    move = MoveDef(name="Pound", chrooked_id="pound", type="Normal", category="physical",
                   power=40, accuracy=100, pp=35)
    c = _move_entry("MOVE_POUND", move, ResolutionMap())
    assert ".effect = EFFECT_HIT," in c
    assert ".target = MOVE_TARGET_SELECTED," in c
    assert ".additionalEffects" not in c
    assert "= TRUE," not in c  # no flag lines


def test_loader_rejects_unknown_flag(tmp_path: Path) -> None:
    import pytest

    root = tmp_path / "ruleset"
    (root / "moves").mkdir(parents=True)
    (root / "moves" / "x.yaml").write_text(
        "name: X\nchrooked_id: x\naka: { pokeemerald: MOVE_X }\ntype: Fire\n"
        "category: physical\nflags: [contact, contcat]\n",  # 'contcat' is a typo
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown flag"):
        Ruleset.load(root)


@pytest.mark.unit
def test_loader_accepts_and_rejects_target(tmp_path: Path) -> None:
    root = tmp_path / "ruleset"
    (root / "moves").mkdir(parents=True)
    (root / "moves" / "x.yaml").write_text(
        "name: X\nchrooked_id: x\naka: { pokeemerald: MOVE_X }\ntype: Fire\n"
        "category: physical\ntarget: both\n",
        encoding="utf-8",
    )
    rs = Ruleset.load(root)
    assert rs.moves["x"].target == "both"

    (root / "moves" / "x.yaml").write_text(
        "name: X\nchrooked_id: x\naka: { pokeemerald: MOVE_X }\ntype: Fire\n"
        "category: physical\ntarget: garbage\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown target"):
        Ruleset.load(root)


def test_apply_report_unaffected_and_loader_validates_bad_addl_effect(tmp_path: Path) -> None:
    # An additional_effects entry with an unknown field fails fast at load.
    root = tmp_path / "ruleset"
    (root / "moves").mkdir(parents=True)
    (root / "moves" / "x.yaml").write_text(
        "name: X\nchrooked_id: x\naka: { pokeemerald: MOVE_X }\ntype: Fire\n"
        "category: physical\nadditional_effects:\n  - { effect: burn, chance: 10, oops: 1 }\n",
        encoding="utf-8",
    )
    import pytest

    with pytest.raises(ValueError, match="unknown field"):
        Ruleset.load(root)
