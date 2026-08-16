"""The pokeemerald applier honors per-Target holds: a held (chrooked_id, category)
is reported `held` and the target file is not written."""

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.pokeemerald.creation import create_owned_content
from chrooked_pokedex.appliers.pokeemerald.learnset_apply import apply_learnsets
from chrooked_pokedex.appliers.pokeemerald.move_apply import apply_moves
from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.appliers.pokeemerald.species_apply import apply_species
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.holds import HoldSet
from chrooked_pokedex.report import ApplyReport


def _build_target(tmp_path: Path) -> Path:
    target = tmp_path / "fork"
    pokemon = target / "src" / "data" / "pokemon"
    learnsets = pokemon / "level_up_learnsets"
    learnsets.mkdir(parents=True)
    (pokemon / "species_info.h").write_text(
        """\
const struct SpeciesInfo gSpeciesInfo[] =
{
    [SPECIES_GOODRA] =
    {
        .baseHP = 90,
        .types = MON_TYPES(TYPE_DRAGON),
        .levelUpLearnset = sGoodraLevelUpLearnset,
    },
};
""",
        encoding="utf-8",
    )
    (learnsets / "gen_1.h").write_text(
        """\
static const struct LevelUpMove sGoodraLevelUpLearnset[] = {
    LEVEL_UP_MOVE( 1, MOVE_DRAGON_BREATH),
    LEVEL_UP_END
};
""",
        encoding="utf-8",
    )
    data = target / "src" / "data"
    (data / "moves_info.h").write_text(
        """\
    [MOVE_DRAGON_BREATH] = { .name = COMPOUND_STRING("Dragon Breath"), .type = TYPE_DRAGON, .category = DAMAGE_CATEGORY_SPECIAL, .power = 60, },
""",
        encoding="utf-8",
    )
    (data / "abilities.h").write_text("// empty\n", encoding="utf-8")
    (data / "types_info.h").write_text(
        """\
#define X UQ_4_12
#define ______ X(1.0)
const uq4_12_t gTypeEffectivenessTable[N][N] =
{
    [TYPE_WATER] = {______},
    [TYPE_DRAGON] = {______},
};
""",
        encoding="utf-8",
    )
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "moves").mkdir(parents=True)
    (root / "abilities").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "species" / "goodra.yaml").write_text(
        """\
name: Goodra
chrooked_id: goodra
aka: { pokeemerald: SPECIES_GOODRA }
types: [Water, Dragon]
learnset:
  - { level: 1, move: Dragon Breath }
  - { level: 20, move: Dragon Breath }
""",
        encoding="utf-8",
    )
    (root / "moves" / "dragonbreath.yaml").write_text(
        """\
name: Dragon Breath
chrooked_id: dragonbreath
aka: { pokeemerald: MOVE_DRAGON_BREATH }
type: Dragon
category: special
power: 80
""",
        encoding="utf-8",
    )
    (root / "abilities" / "deadlock.yaml").write_text(
        """\
name: Deadlock
chrooked_id: deadlock
aka: { pokeemerald: ABILITY_DEADLOCK }
description: Traps and slows foes.
""",
        encoding="utf-8",
    )
    return Ruleset.load(root)


def _held(report: ApplyReport, category: str, chrooked_id: str) -> bool:
    return any(
        e.status == "held" and e.category == category and e.chrooked_id == chrooked_id
        for e in report.entries
    )


@pytest.mark.unit
def test_species_hold_keeps_target_data(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    before = (target / "src" / "data" / "pokemon" / "species_info.h").read_text()
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_species(
        target, ruleset, resmap, report,
        holds=HoldSet(held={"goodra": frozenset({"species"})}),
    )

    assert not changed
    assert (target / "src" / "data" / "pokemon" / "species_info.h").read_text() == before
    assert _held(report, "species", "goodra")


@pytest.mark.unit
def test_learnset_hold_keeps_target_list(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    learnset_path = target / "src" / "data" / "pokemon" / "level_up_learnsets" / "gen_1.h"
    before = learnset_path.read_text()
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_learnsets(
        target, ruleset, resmap, report,
        holds=HoldSet(held={"goodra": frozenset({"learnset"})}),
    )

    assert not changed
    assert learnset_path.read_text() == before
    assert _held(report, "learnset", "goodra")


@pytest.mark.unit
def test_move_hold_keeps_target_move(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    moves_path = target / "src" / "data" / "moves_info.h"
    before = moves_path.read_text()
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_moves(
        target, ruleset, resmap, report,
        holds=HoldSet(held={"dragonbreath": frozenset({"moves"})}),
    )

    assert not changed
    assert moves_path.read_text() == before
    assert _held(report, "move", "dragonbreath")


@pytest.mark.unit
def test_creation_hold_skips_owned_ability(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    create_owned_content(
        target, ruleset, resmap, report,
        holds=HoldSet(held={"deadlock": frozenset({"abilities"})}),
    )

    assert _held(report, "ability", "deadlock")
    # The held ability was neither registered nor written.
    assert resmap.ability("Deadlock") is None
    assert "DEADLOCK" not in (target / "src" / "data" / "abilities.h").read_text()
