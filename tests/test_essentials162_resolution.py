"""ac3: every lookup resolves by InternalName; the Spanish display Name does not match.

The map is built from the committed 16.2 fixtures. A move/ability/species resolves via
its INTERNAL name (MEGAHORN, STENCH, BULBASAUR); resolving via the Spanish display Name
(Megacuerno, Hedor) must NOT match. An `aka:` essentials hint still wins for species.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from chrooked_pokedex.appliers.essentials162.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "essentials162"
    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    for name in ("pokemon.txt", "types.txt", "moves.txt", "abilities.txt"):
        shutil.copy(_FIXTURES / name, pbs / name)
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "species" / "bulbasaur.yaml").write_text(
        "name: Bulbasaur\nchrooked_id: bulbasaur\n", encoding="utf-8"
    )
    (root / "species" / "goodra.yaml").write_text(
        "name: Goodra\nchrooked_id: goodra\naka: { essentials: GOODRA_HISUI }\n",
        encoding="utf-8",
    )
    return Ruleset.load(root)


def test_move_resolves_by_internalname_not_spanish(tmp_path):
    resmap = build_resolution_map(_target(tmp_path), _ruleset(tmp_path))
    assert resmap.move("MEGAHORN") == "MEGAHORN"
    # The Spanish display Name must not resolve — that is the 16.2 identity split.
    assert resmap.move("Megacuerno") is None
    assert resmap.move("Excalibur") is None  # genuinely unknown stays unresolved


def test_ability_resolves_by_internalname_not_spanish(tmp_path):
    resmap = build_resolution_map(_target(tmp_path), _ruleset(tmp_path))
    assert resmap.ability("STENCH") == "STENCH"
    assert resmap.ability("Hedor") is None  # Spanish display Name does not match


def test_type_resolves_by_internalname_not_spanish(tmp_path):
    resmap = build_resolution_map(_target(tmp_path), _ruleset(tmp_path))
    assert resmap.type("NORMAL") == "NORMAL"
    assert resmap.type("FIGHTING") == "FIGHTING"
    assert resmap.type("Lucha") is None  # Spanish display Name (FIGHTING) does not match


def test_species_resolves_by_id_and_aka_hint_wins(tmp_path):
    resmap = build_resolution_map(_target(tmp_path), _ruleset(tmp_path))
    # No hint -> derived from name (BULBASAUR).
    assert resmap.species("bulbasaur", {}) == "BULBASAUR"
    # An essentials aka: hint still wins.
    assert resmap.species("goodra", {"essentials": "GOODRA_HISUI"}) == "GOODRA_HISUI"


def test_standard_types_seed_when_types_file_absent(tmp_path):
    target = tmp_path / "essentials162"
    (target / "PBS").mkdir(parents=True)
    (target / "PBS" / "pokemon.txt").write_bytes(b"[1]\r\nInternalName=BULBASAUR\r\n")
    resmap = build_resolution_map(target, _ruleset(tmp_path))
    assert resmap.type("Fairy") == "FAIRY"
    assert resmap.type("Cosmic") is None
