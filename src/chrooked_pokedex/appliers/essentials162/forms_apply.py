"""Apply species scalar Overrides into an Essentials 16.2 `PBS/pokemonforms.txt`.

The alt-form sibling of `species_apply`. A Ruleset alt-form is named `<Base> <Token>`
("Kangaskhan Mega", "Deoxys Attack", "Deerling Summer"). This resolver:

  1. splits the name into a base and a trailing form token,
  2. resolves the base to a target form-file base (the `[BASE-N]` header prefix), and
  3. picks the one `[BASE-N]` section whose `FormName` contains the token.

A unique match is field-edited in place (same field rules as `species_apply`: per-stat
BaseStats with Speed at index 3, Type1/Type2 with mono-type Type2 drop, comma
`Abilities` + singular `HiddenAbility`). When a base has MORE than one form whose
FormName matches the token, the form is blocked — never guessed. A token that matches
NO form here is left untouched: it is the base/default form that `species_apply` owns
(e.g. "Deerling Spring" → the base `[N]` in `pokemon.txt`), or a genuinely-absent
species.

`apply_forms` returns the changed paths AND the set of chrooked_ids it claimed, so the
caller can tell `species_apply` to skip them and avoid a duplicate blocked entry.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import SpeciesOverride
from ...report import ApplyReport, ReportEntry
from ...seed.neutralize import slug as _norm
from . import forms_edit, forms_read, pbs_io
from .resolution import ResolutionMap

# 16.2 BaseStats order is HP, Attack, Defense, Speed, Sp.Atk, Sp.Def — Speed at index 3.
_STAT_KEY_TO_INDEX = {"hp": 0, "atk": 1, "def": 2, "spe": 3, "spa": 4, "spd": 5}
_ABILITY_SLOTS = ("primary", "secondary")


def apply_forms(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> tuple[set[Path], set[str]]:
    path = target / "PBS" / "pokemonforms.txt"
    if not path.exists():
        return set(), set()
    text, had_bom = pbs_io.read(path)
    original = text
    sections = forms_read.parse_form_sections(text)
    handled: set[str] = set()

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        if not (override.types or override.abilities or override.stats):
            continue
        # An explicit essentials alias resolves against pokemon.txt — that is
        # species_apply's job, not a form match. Respect it and move on.
        if (override.aka or {}).get("essentials"):
            continue
        base_name, token = _split_form_name(override.name)
        if token is None:
            continue  # single-token name — not an alt-form

        base_norm = _norm(base_name)
        token_norm = _norm(token)
        matches = [
            s for s in sections
            if _norm(s.base) == base_norm
            and s.form_name is not None
            and token_norm in _form_name_words(s.form_name)
        ]
        if not matches:
            continue  # base/default form (species_apply owns it) or genuinely absent
        if len(matches) > 1:
            report.add(ReportEntry(
                status="blocked", category="species", chrooked_id=chrooked_id,
                reason=(
                    f"form token {token!r} matches {len(matches)} forms of "
                    f"{base_name!r} ({', '.join(m.header for m in matches)}); "
                    "ambiguous, not applied"
                ),
            ))
            handled.add(chrooked_id)
            continue

        header = matches[0].header
        text, unresolved = _apply_form_fields(text, header, override, resmap)
        handled.add(chrooked_id)
        if unresolved:
            report.add(ReportEntry(
                status="partial", category="species", chrooked_id=chrooked_id,
                symbol=header, reason="some fields not applied",
                partial_fields=tuple(unresolved),
            ))
        else:
            report.add(ReportEntry(
                status="applied", category="species", chrooked_id=chrooked_id,
                symbol=header,
            ))

    if text != original:
        pbs_io.write(path, text, had_bom)
        return {path}, handled
    return set(), handled


def _split_form_name(name: str) -> tuple[str, str | None]:
    """Split a `<Base> <Token>` form name into (base, token).

    The token is the LAST whitespace-separated word ("Kangaskhan Mega" -> "Mega");
    the base is everything before it. This single-word-token convention is sufficient
    because the Ruleset names every alt-form as `<Base species> <one form word>`
    (Mega/Attack/Summer/Resolute/...). A single-word name has no token (returns None).
    """
    parts = name.split()
    if len(parts) < 2:
        return name, None
    return " ".join(parts[:-1]), parts[-1]


def _form_name_words(form_name: str) -> set[str]:
    """The normalized WHOLE words of a FormName, for whole-word token matching.

    Matching the token against whole words — not a substring of the concatenated
    name — stops a short token like "heat" matching "Overheat" while still letting
    "mega" match the multi-word `FormName=Mega Kangaskhan`.
    """
    return {_norm(word) for word in form_name.split()} - {""}


def _apply_form_fields(
    text: str, header: str, override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    unresolved: list[str] = []

    if override.types:
        text, type_unresolved = _apply_types(text, header, override, resmap)
        unresolved.extend(type_unresolved)

    if override.stats:
        for key, value in override.stats.items():
            index = _STAT_KEY_TO_INDEX.get(key)
            if index is None:
                unresolved.append(f"stat:{key}")
                continue
            text, applied = forms_edit.set_comma_index(
                text, header, "BaseStats", index, str(value)
            )
            if not applied:
                unresolved.append(f"stat:{key}")

    if override.abilities:
        text, ability_unresolved = _apply_abilities(text, header, override, resmap)
        unresolved.extend(ability_unresolved)

    return text, unresolved


def _apply_types(
    text: str, header: str, override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    symbols = [resmap.type(name) for name in override.types]
    if not all(symbols):
        return text, ["types"]
    text, applied = forms_edit.set_section_field(text, header, "Type1", symbols[0])
    if not applied:
        return text, ["types"]
    if len(symbols) > 1:
        text, _ = forms_edit.set_section_field(text, header, "Type2", symbols[1])
    else:
        # mono-type: 16.2 drops Type2 entirely, never leaves a blank `Type2=`.
        text, _ = forms_edit.remove_section_field(text, header, "Type2")
    return text, []


def _apply_abilities(
    text: str, header: str, override: SpeciesOverride, resmap: ResolutionMap
) -> tuple[str, list[str]]:
    unresolved: list[str] = []
    current = forms_edit.get_section_field(text, header, "Abilities") or ""
    slots = [a.strip() for a in current.split(",") if a.strip()]
    wrote_slot = False
    for index, slot in enumerate(_ABILITY_SLOTS):
        name = getattr(override.abilities, slot)
        if name is None:
            continue
        resolved = resmap.ability(name)
        if resolved is None:
            # Do NOT fabricate an undefined ability reference — Essentials refuses to
            # compile it. Report and skip; the species stays partial.
            unresolved.append(f"ability:{name}")
            continue
        while len(slots) <= index:
            slots.append("")
        slots[index] = resolved
        wrote_slot = True
    # Strip only TRAILING empties — an interior gap (e.g. an unwritten primary slot)
    # must NOT collapse and promote a later ability into the wrong slot.
    while slots and not slots[-1]:
        slots.pop()
    if wrote_slot and slots:
        text, _ = forms_edit.set_section_field(text, header, "Abilities", ",".join(slots))

    if override.abilities.hidden is not None:
        # HiddenAbility is SINGULAR in 16.2 — one value, never a comma list.
        resolved = resmap.ability(override.abilities.hidden)
        if resolved is None:
            unresolved.append(f"hidden-ability:{override.abilities.hidden}")
        else:
            text, _ = forms_edit.set_section_field(text, header, "HiddenAbility", resolved)

    return text, unresolved
