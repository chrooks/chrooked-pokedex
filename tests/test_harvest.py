"""Milestone 6 — gated reverse sync: harvest proposes per-field Ruleset edits."""

from pathlib import Path

from chrooked_pokedex.appliers.pokeemerald.resolution import build_resolution_map
from chrooked_pokedex.harvest.harvester import apply_proposals, propose_changes
from chrooked_pokedex.model import Ruleset


def _fork(tmp_path: Path, speed: int) -> Path:
    fork = tmp_path / "fork"
    pokemon = fork / "src" / "data" / "pokemon"
    pokemon.mkdir(parents=True)
    (pokemon / "species_info.h").write_text(
        f"""\
    [SPECIES_GOODRA] =
    {{
        .baseHP = 90,
        .baseSpeed = {speed},
        .types = MON_TYPES(TYPE_WATER, TYPE_DRAGON),
    }},
""",
        encoding="utf-8",
    )
    return fork


def _ruleset(tmp_path: Path) -> tuple[Path, Ruleset]:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    (root / "species" / "goodra.yaml").write_text(
        """\
name: Goodra
chrooked_id: goodra
aka: { pokeemerald: SPECIES_GOODRA }
types: [Water, Dragon]
stats: { spe: 80 }
""",
        encoding="utf-8",
    )
    return root, Ruleset.load(root)


def test_harvest_finds_single_changed_stat(tmp_path: Path) -> None:
    # The Ruleset records spe: 80; the fork now has spe: 95 — one drifted field.
    fork = _fork(tmp_path, speed=95)
    root, ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(fork, ruleset)

    proposals = propose_changes(fork, ruleset, resmap)

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.chrooked_id == "goodra"
    assert proposal.kind == "stat"
    assert proposal.key == "spe"
    assert proposal.ruleset_value == 80
    assert proposal.fork_value == 95


def test_harvest_no_drift_when_fork_matches_ruleset(tmp_path: Path) -> None:
    fork = _fork(tmp_path, speed=80)  # matches the Ruleset
    root, ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(fork, ruleset)

    assert propose_changes(fork, ruleset, resmap) == []


def test_declining_leaves_ruleset_untouched(tmp_path: Path) -> None:
    fork = _fork(tmp_path, speed=95)
    root, ruleset = _ruleset(tmp_path)
    before = (root / "species" / "goodra.yaml").read_text()

    # Accept nothing.
    touched = apply_proposals(root, ruleset, accepted=[])

    assert touched == set()
    assert (root / "species" / "goodra.yaml").read_text() == before


def test_accepting_updates_only_that_field(tmp_path: Path) -> None:
    fork = _fork(tmp_path, speed=95)
    root, ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(fork, ruleset)
    proposals = propose_changes(fork, ruleset, resmap)

    apply_proposals(root, ruleset, accepted=proposals)

    updated = Ruleset.load(root)
    goodra = updated.species["goodra"]
    assert goodra.stats == {"spe": 95}  # the one field changed
    assert goodra.types == ("Water", "Dragon")  # everything else preserved
