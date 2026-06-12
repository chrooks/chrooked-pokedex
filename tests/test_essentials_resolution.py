"""Essentials Resolution map + neutral->Essentials vocab translation.

Resolution turns a `chrooked_id` / plain name into the target project's INTERNAL
name (`goodra` -> `GOODRA`, `Water` -> `WATER`). The vocab maps translate the
Ruleset's neutral move fields into Essentials' own spellings, and — crucially —
return None for anything they cannot honestly translate, so the caller reports it
unresolved instead of inventing a token.
"""

from pathlib import Path

from chrooked_pokedex.appliers.essentials import vocab
from chrooked_pokedex.appliers.essentials.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "essentials"
    _write(target, "PBS/pokemon.txt", "[BULBASAUR]\nName = Bulbasaur\n")
    _write(target, "PBS/moves.txt", "[FLAMETHROWER]\nName = Flamethrower\nType = FIRE\n")
    _write(target, "PBS/abilities.txt", "[OVERGROW]\nName = Overgrow\n")
    _write(target, "PBS/types.txt", "[FIRE]\nName = Fire\n[WATER]\nName = Water\n")
    return target


def _ruleset(tmp_path: Path) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "species" / "goodra.yaml").write_text(
        "name: Goodra\nchrooked_id: goodra\naka: { pokeemerald: SPECIES_GOODRA }\n",
        encoding="utf-8",
    )
    return Ruleset.load(root)


# --- vocab ---------------------------------------------------------------------

def test_vocab_type_and_category():
    assert vocab.type_internal("Water") == "WATER"
    assert vocab.type_internal("Mr Mime") == "MRMIME"  # non-alnum stripped
    assert vocab.category("physical") == "Physical"
    assert vocab.category("status") == "Status"


def test_vocab_flag_maps_known_and_refuses_unknown():
    assert vocab.flag("contact") == "Contact"
    assert vocab.flag("biting") == "Biting"
    # No standard Essentials flag for these -> honest None, caller marks unresolved.
    assert vocab.flag("bone") is None
    assert vocab.flag("hammer") is None


def test_vocab_primary_effect_hit_is_none_functioncode():
    assert vocab.function_code("hit") == "None"
    # A parameterised primary effect cannot be faithfully ported -> None (unresolved).
    assert vocab.function_code("super_effective_on_arg") is None


def test_vocab_additional_effect_functioncode():
    assert vocab.additional_function_code("burn") == "BurnTarget"
    assert vocab.additional_function_code("paralysis") == "ParalyzeTarget"
    assert vocab.additional_function_code("totally_made_up") is None


# --- resolution ----------------------------------------------------------------

def test_resolution_resolves_species_move_ability_type(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)

    # species: constructed from display name when no essentials aka hint.
    assert resmap.species("goodra", {"pokeemerald": "SPECIES_GOODRA"}) == "GOODRA"
    # move/ability resolve by display name to the target's INTERNAL header.
    assert resmap.move("Flamethrower") == "FLAMETHROWER"
    assert resmap.ability("Overgrow") == "OVERGROW"
    # type resolves from the target's own types.txt...
    assert resmap.type("Water") == "WATER"
    # ...but a type the target lacks is unresolved (None), never fabricated — else a
    # Fakemon type would be written as a token Essentials rejects.
    assert resmap.type("Cosmic") is None
    # an unknown move is unresolved, never guessed.
    assert resmap.move("Excalibur") is None


def test_resolution_seeds_standard_types_when_types_file_absent(tmp_path):
    # With no types.txt to parse, the 18 standard types still resolve (a safety net
    # mirroring the pokeemerald applier), but a non-standard one stays unresolved.
    target = tmp_path / "essentials"
    _write(target, "PBS/pokemon.txt", "[BULBASAUR]\nName = Bulbasaur\n")
    resmap = build_resolution_map(target, _ruleset(tmp_path))
    assert resmap.type("Fairy") == "FAIRY"
    assert resmap.type("Water") == "WATER"
    assert resmap.type("Cosmic") is None


def test_resolution_prefers_essentials_aka_hint(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path)
    resmap = build_resolution_map(target, ruleset)
    assert resmap.species("goodra", {"essentials": "GOODRA_HISUI"}) == "GOODRA_HISUI"
