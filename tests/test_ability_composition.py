"""Composition of abilities from behaviors (#98).

`behaviors:` on an ability yaml is not a combo-specific field — it is the
general answer to "which behaviors does this ability have". Absent means its
own; one non-self entry is an alias; two or more is a combo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.model.ruleset import Ruleset
from chrooked_pokedex.model.schema import AbilityDef, composed_behaviors, is_composed

pytestmark = pytest.mark.unit

RULESET = Path(__file__).resolve().parents[1] / "ruleset"


def _write(dirpath: Path, ident: str, body: str) -> None:
    (dirpath / "abilities").mkdir(parents=True, exist_ok=True)
    (dirpath / "abilities" / f"{ident}.yaml").write_text(body, encoding="utf-8")


def _ability(ident: str, parts: str = "") -> str:
    line = f"behaviors: [{parts}]\n" if parts else ""
    return f"name: {ident.title()}\nchrooked_id: {ident}\ndescription: x\n{line}"


# --- resolution -------------------------------------------------------------

def test_absent_key_resolves_to_own_behavior():
    a = AbilityDef(name="Solar Power", chrooked_id="solarpower")
    assert composed_behaviors(a) == ("solarpower",)
    assert not is_composed(a)


def test_single_non_self_entry_is_an_alias():
    a = AbilityDef(name="Sunforge", chrooked_id="sunforge", behaviors=("solarpower",))
    assert composed_behaviors(a) == ("solarpower",)
    assert is_composed(a)


def test_two_entries_is_a_combo_and_keeps_order():
    a = AbilityDef(
        name="Solar Dynamo", chrooked_id="solardynamo",
        behaviors=("solarpower", "drought"),
    )
    assert composed_behaviors(a) == ("solarpower", "drought")
    assert is_composed(a)


def test_explicit_self_reference_is_not_composed():
    a = AbilityDef(name="Solar Power", chrooked_id="solarpower", behaviors=("solarpower",))
    assert not is_composed(a)


# --- the real ruleset still loads ------------------------------------------

def test_every_shipped_ability_loads_unchanged():
    r = Ruleset.load(RULESET)
    assert len(r.abilities) >= 99
    for ability in r.abilities.values():
        assert composed_behaviors(ability)  # never empty


# --- validation -------------------------------------------------------------

def test_unknown_part_is_rejected(tmp_path):
    _write(tmp_path, "combo", _ability("combo", "solarpower, notathing"))
    _write(tmp_path, "solarpower", _ability("solarpower"))
    with pytest.raises(ValueError, match="notathing"):
        Ruleset.load(tmp_path)


def test_duplicate_part_is_rejected(tmp_path):
    _write(tmp_path, "combo", _ability("combo", "solarpower, solarpower"))
    _write(tmp_path, "solarpower", _ability("solarpower"))
    with pytest.raises(ValueError, match="duplicate"):
        Ruleset.load(tmp_path)


def test_two_step_cycle_is_rejected(tmp_path):
    _write(tmp_path, "alpha", _ability("alpha", "beta"))
    _write(tmp_path, "beta", _ability("beta", "alpha"))
    with pytest.raises(ValueError, match="cycle"):
        Ruleset.load(tmp_path)


def test_deep_cycle_is_rejected(tmp_path):
    _write(tmp_path, "alpha", _ability("alpha", "beta"))
    _write(tmp_path, "beta", _ability("beta", "gamma"))
    _write(tmp_path, "gamma", _ability("gamma", "alpha"))
    with pytest.raises(ValueError, match="cycle"):
        Ruleset.load(tmp_path)


def test_a_vanilla_part_needs_only_an_ability_file(tmp_path):
    """Drought has no behavior spec and must not be forced to grow one."""
    _write(tmp_path, "drought", _ability("drought"))
    _write(tmp_path, "solarpower", _ability("solarpower"))
    _write(tmp_path, "solardynamo", _ability("solardynamo", "solarpower, drought"))
    r = Ruleset.load(tmp_path)
    assert composed_behaviors(r.abilities["solardynamo"]) == ("solarpower", "drought")


def test_error_names_the_offending_file(tmp_path):
    _write(tmp_path, "combo", _ability("combo", "ghost"))
    with pytest.raises(ValueError, match=r"abilities/combo\.yaml"):
        Ruleset.load(tmp_path)


# --- the dex round-trips a composition -------------------------------------

def test_merged_view_carries_behaviors_so_an_edit_cannot_reset_them(tmp_path):
    """Without this the editor reads `behaviors ?? []` and a save would quietly
    turn a composed ability back into a plain one."""
    from chrooked_pokedex.web.dex import build_abilities

    _write(tmp_path, "solarpower", _ability("solarpower"))
    _write(tmp_path, "drought", _ability("drought"))
    _write(tmp_path, "solardynamo", _ability("solardynamo", "solarpower, drought"))
    r = Ruleset.load(tmp_path)
    rows = {row["chrooked_id"]: row for row in build_abilities({}, r)}
    assert rows["solardynamo"]["behaviors"] == ["solarpower", "drought"]
    assert rows["solarpower"]["behaviors"] == []
