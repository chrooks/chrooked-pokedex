"""Forms-file applier tests for the Essentials 16.2 dialect (#60 Bucket A).

`pokemonforms.txt` keys each alt-form by a `[BASE-N]` header carrying a `FormName=`
and NO `InternalName`, so neither the numeric-section reader nor the `aka.essentials`
alias can reach it. `forms_apply` resolves a Ruleset form by matching its
`<Base> <Token>` name to the `[BASE-N]` section whose `FormName` contains the token,
then field-edits that section in place — and blocks (never guesses) when a base has
more than one form whose `FormName` matches the token.

The fixture `pokemonforms.txt` carries Mega Kangaskhan, the three Deoxys formes, a
Deerling Summer form, and a synthetic two-form Rotom base used only to exercise the
ambiguous-match block.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from chrooked_pokedex.appliers.essentials162 import forms_apply, pbs_io, resolution
from chrooked_pokedex.model.schema import AbilitiesOverride, SpeciesOverride
from chrooked_pokedex.report import ApplyReport

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"


class _Ruleset:
    def __init__(self, species=None):
        self.species = species or {}


def _target(tmp_path: Path) -> Path:
    pbs = tmp_path / "PBS"
    pbs.mkdir()
    for name in ("pokemon.txt", "pokemonforms.txt", "types.txt", "abilities.txt", "moves.txt"):
        shutil.copy(_FIXTURES / name, pbs / name)
    return tmp_path


def _apply(target: Path, ruleset) -> tuple[ApplyReport, set, set]:
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed, handled = forms_apply.apply_forms(target, ruleset, resmap, report)
    return report, changed, handled


def _forms_text(target: Path) -> str:
    text, _ = pbs_io.read(target / "PBS" / "pokemonforms.txt")
    return text


def test_form_stat_override_lands_on_matched_form_section(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset({
        "kangaskhanmega": SpeciesOverride(
            name="Kangaskhan Mega", chrooked_id="kangaskhanmega", stats={"def": 105, "spd": 105},
        ),
    })
    report, changed, handled = _apply(target, ruleset)

    text = _forms_text(target)
    # 16.2 BaseStats order HP,Atk,Def,Spe,SpA,SpD — Def at index 2, SpD at index 5.
    assert "BaseStats=105,125,105,100,60,105" in text
    assert "kangaskhanmega" in handled
    assert changed
    assert any(e.chrooked_id == "kangaskhanmega" and e.status == "applied" for e in report.entries)


def test_form_ability_and_type_override(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset({
        "deoxysattack": SpeciesOverride(
            name="Deoxys Attack", chrooked_id="deoxysattack",
            abilities=AbilitiesOverride(primary="Stench"),
        ),
    })
    report, _, handled = _apply(target, ruleset)
    text = _forms_text(target)
    section = text.split("[DEOXYS-1]")[1].split("[DEOXYS-2]")[0]
    assert "Abilities=STENCH" in section
    assert "deoxysattack" in handled


def test_default_form_token_not_in_any_formname_is_skipped(tmp_path):
    # "Deerling Spring" — the Spring form is the base [N] in pokemon.txt, so no
    # DEERLING-N FormName contains "spring". forms_apply must not match it here.
    target = _target(tmp_path)
    before = _forms_text(target)
    ruleset = _Ruleset({
        "deerlingspring": SpeciesOverride(
            name="Deerling Spring", chrooked_id="deerlingspring",
            abilities=AbilitiesOverride(hidden="Forestry"),
        ),
    })
    report, changed, handled = _apply(target, ruleset)
    assert "deerlingspring" not in handled
    assert _forms_text(target) == before
    assert not changed


def test_ambiguous_formname_match_blocks(tmp_path):
    # Rotom base has two forms whose FormName contains "twin"; a Ruleset form named
    # "Rotom Twin" cannot be disambiguated, so it must block, not guess.
    target = _target(tmp_path)
    before = _forms_text(target)
    ruleset = _Ruleset({
        "rotomtwin": SpeciesOverride(name="Rotom Twin", chrooked_id="rotomtwin", stats={"atk": 99}),
    })
    report, changed, handled = _apply(target, ruleset)
    assert "rotomtwin" in handled  # claimed (so species_apply won't also touch it)
    assert _forms_text(target) == before  # but nothing written
    assert any(e.chrooked_id == "rotomtwin" and e.status == "blocked" for e in report.entries)


def test_partial_token_does_not_match_a_whole_form_word(tmp_path):
    # "Deoxys Atta" must NOT match FormName "Attack Forme" — the token is matched as a
    # WHOLE word, not a substring, so a partial/typo'd token resolves to nothing here.
    target = _target(tmp_path)
    before = _forms_text(target)
    ruleset = _Ruleset({
        "deoxysatta": SpeciesOverride(
            name="Deoxys Atta", chrooked_id="deoxysatta", stats={"atk": 200},
        ),
    })
    _, changed, handled = _apply(target, ruleset)
    assert "deoxysatta" not in handled
    assert _forms_text(target) == before
    assert not changed


def test_mono_type_override_drops_type2(tmp_path):
    # DEERLING-1 (Summer) is NORMAL/GRASS; a mono-type Override writes Type1 and
    # removes Type2 entirely — 16.2 never leaves a blank `Type2=`.
    target = _target(tmp_path)
    ruleset = _Ruleset({
        "deerlingsummer": SpeciesOverride(
            name="Deerling Summer", chrooked_id="deerlingsummer", types=("Fire",),
        ),
    })
    _, _, handled = _apply(target, ruleset)
    text = _forms_text(target)
    section = text.split("[DEERLING-1]")[1].split("#----")[0]
    assert "Type1=FIRE" in section
    assert "Type2=" not in section
    assert "deerlingsummer" in handled


def test_aka_essentials_species_is_left_for_species_apply(tmp_path):
    # A species already aliased to a real InternalName resolves against pokemon.txt;
    # forms_apply must leave it alone even if its name looks form-shaped.
    target = _target(tmp_path)
    before = _forms_text(target)
    ruleset = _Ruleset({
        "deerlingsummer": SpeciesOverride(
            name="Deerling Summer", chrooked_id="deerlingsummer",
            aka={"essentials": "DEERLING"},
            stats={"spe": 80},
        ),
    })
    report, _, handled = _apply(target, ruleset)
    assert "deerlingsummer" not in handled
    assert _forms_text(target) == before
