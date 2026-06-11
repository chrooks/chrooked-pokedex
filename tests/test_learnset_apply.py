"""Milestone 4 — learnsets applied by whole-list replace; no duplicate moves."""

from pathlib import Path

from chrooked_pokedex.appliers.pokeemerald.learnset_apply import apply_learnsets
from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.readers.pokeemerald.learnset_parser import (
    LearnsetEntry,
    parse_learnsets,
)
from chrooked_pokedex.report import ApplyReport


def _build_target(tmp_path: Path) -> Path:
    target = tmp_path / "fork"
    pokemon = target / "src" / "data" / "pokemon"
    learnsets = pokemon / "level_up_learnsets"
    learnsets.mkdir(parents=True)
    # Existing Goodra list ALREADY contains Dragon Breath — the v1 merge bug
    # would duplicate it.
    (learnsets / "gen_1.h").write_text(
        """\
static const struct LevelUpMove sGoodraLevelUpLearnset[] = {
    LEVEL_UP_MOVE( 1, MOVE_DRAGON_BREATH),
    LEVEL_UP_MOVE(10, MOVE_TACKLE),
    LEVEL_UP_END
};
""",
        encoding="utf-8",
    )
    (pokemon / "species_info.h").write_text(
        """\
    [SPECIES_GOODRA] =
    {
        .baseHP = 90,
        .levelUpLearnset = sGoodraLevelUpLearnset,
    },
""",
        encoding="utf-8",
    )
    # A move table so MOVE names resolve. Excalibur is intentionally absent.
    (target / "src" / "data").mkdir(parents=True, exist_ok=True)
    (target / "src" / "data" / "moves_info.h").write_text(
        """\
    [MOVE_DRAGON_BREATH] = { .name = COMPOUND_STRING("Dragon Breath"), .type = TYPE_DRAGON, .category = DAMAGE_CATEGORY_SPECIAL, },
    [MOVE_LIQUIDATION] = { .name = COMPOUND_STRING("Liquidation"), .type = TYPE_WATER, .category = DAMAGE_CATEGORY_PHYSICAL, },
""",
        encoding="utf-8",
    )
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "moves").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    # Goodra learnset also contains Dragon Breath, plus Liquidation and the
    # Ruleset-owned Excalibur (not in the target yet).
    (root / "species" / "goodra.yaml").write_text(
        """\
name: Goodra
chrooked_id: goodra
aka: { pokeemerald: SPECIES_GOODRA }
learnset:
  - { level: 1, move: Dragon Breath }
  - { level: 30, move: Liquidation }
  - { level: 45, move: Excalibur }
""",
        encoding="utf-8",
    )
    (root / "moves" / "excalibur.yaml").write_text(
        """\
name: Excalibur
chrooked_id: excalibur
aka: { pokeemerald: MOVE_EXCALIBUR }
type: Steel
category: physical
power: 90
""",
        encoding="utf-8",
    )
    return Ruleset.load(root)


def test_learnset_whole_list_replace_no_duplicate(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_learnsets(target, ruleset, resmap, report)

    learnsets = parse_learnsets(target)
    goodra = learnsets["SPECIES_GOODRA"]
    # Dragon Breath appears exactly once — the merge bug would make it twice.
    dragon_breath = [e for e in goodra if e.move == "MOVE_DRAGON_BREATH"]
    assert len(dragon_breath) == 1
    # Liquidation landed; the old Tackle entry is gone (whole-list replace).
    assert LearnsetEntry("MOVE_LIQUIDATION", 30) in goodra
    assert all(e.move != "MOVE_TACKLE" for e in goodra)


def test_learnset_excalibur_partial_until_created(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    apply_learnsets(target, ruleset, resmap, report)

    # Excalibur is Ruleset-owned but not in the target, so Goodra is partial.
    assert report.counts()["partial"] == 1
    entry = report.entries[0]
    assert entry.chrooked_id == "goodra"
    assert any("Excalibur" in field for field in entry.partial_fields)
    # And Excalibur is NOT written into the target (would not compile).
    goodra = parse_learnsets(target)["SPECIES_GOODRA"]
    assert all("EXCALIBUR" not in e.move for e in goodra)


def test_learnset_apply_is_idempotent(tmp_path: Path) -> None:
    target = _build_target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)

    apply_learnsets(target, ruleset, resmap, ApplyReport())
    first = (target / "src/data/pokemon/level_up_learnsets/gen_1.h").read_text()
    second_changed = apply_learnsets(target, ruleset, resmap, ApplyReport())
    second = (target / "src/data/pokemon/level_up_learnsets/gen_1.h").read_text()

    assert first == second
    assert second_changed == set()
