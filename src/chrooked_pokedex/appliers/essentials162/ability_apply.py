"""Apply ability data rows into an Essentials 16.2 `PBS/abilities.txt`.

## Shared core vs dialect-specific row format

The **data-writing core** is the same across dialects:

1. Resolve INTERNAL — `aka.essentials` hint if present, else `vocab.internal_name(name)`.
2. Dedupe edit-vs-create — if a row for INTERNAL already exists, edit cols 2/3 in place;
   otherwise append a new row at `max_index + 1`. Do not duplicate.
3. Register on write — add `resmap.ability_by_name[internal.lower()] = internal` so
   `species_apply` can resolve the newly-written ability in the same run.
4. Report honestly — emit `applied` or `partial`; never fabricate a token that Essentials
   would reject; silence a no-op (nothing changed = no report line).

Only the **row format** differs by dialect:

- 16.2 (this module): flat CSV — `idx,INTERNALNAME,DisplayName,"description"`.
- Modern v21 (deferred): `[NAME]` section block with `Name=`/`Description=`/`Flags=` fields.

## In-engine registration note

Compiling `abilities.txt` IS Essentials 16.2's ability registration step: the row makes
`:NAME` a valid `PBAbilities` constant the engine resolves at boot. `hasWorkingAbility(:NAME)`
can therefore resolve after the next recompile — no separate registration step is required
beyond writing the row.

16.2 abilities.txt is flat positional CSV, 4 columns, BOM + CRLF:

  idx,INTERNALNAME,DisplayName,"description"

Example: `1,STENCH,Hedor,"Debido al mal olor..."`
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...model.schema import AbilityDef
from ...report import ApplyReport, ReportEntry
from ..essentials import vocab
from . import behavior_install
from . import csv_io, pbs_io
from .resolution import ResolutionMap

# Column indices in a 16.2 abilities.txt row.
_IDX_COL = 0
_INTERNAL_COL = 1
_NAME_COL = 2
_DESC_COL = 3

# Total columns in a 16.2 abilities.txt row.
_ROW_WIDTH = 4


def apply_abilities(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    """Write each Ruleset AbilityDef into `PBS/abilities.txt`.

    Runs before `apply_species` so freshly-written abilities are registered in
    `resmap.ability_by_name` and species slots resolve in the same apply run.
    """
    path = target / "PBS" / "abilities.txt"
    if not path.exists():
        return set()
    text, had_bom = pbs_io.read(path)
    original = text

    for chrooked_id in sorted(ruleset.abilities):
        ability = ruleset.abilities[chrooked_id]
        internal = _internal_of(ability)
        if not internal:
            report.add(ReportEntry(
                status="blocked", category="ability", chrooked_id=chrooked_id,
                reason="could not derive INTERNAL name for ability",
            ))
            continue

        # Edit when a row already exists under the resolved symbol or the
        # name-derived internal — never append as a duplicate row.
        symbol = resmap.ability(ability.name) or internal
        if csv_io.find_row(text, symbol) is not None:
            text = _edit_existing(text, symbol, ability, report, chrooked_id)
        else:
            text = _create_row(text, ability, internal, report, chrooked_id)

        # Register into the in-memory map so species_apply resolves this ability
        # in the same run, even before this file is written to disk.
        resmap.ability_by_name[internal.lower()] = internal

    if text != original:
        pbs_io.write(path, text, had_bom)
        return {path}
    return set()


def _edit_existing(
    text: str,
    symbol: str,
    ability: AbilityDef,
    report: ApplyReport,
    chrooked_id: str,
) -> str:
    """Edit display name (col 2) and description (col 3) when they differ.

    When nothing differs, return text unchanged and emit no report line — no churn.
    """
    desired_name = ability.name
    desired_desc = _quote_desc(ability.description)

    current_name = csv_io.get_column(text, symbol, _NAME_COL)
    current_desc = csv_io.get_column(text, symbol, _DESC_COL)

    changed: list[str] = []

    if current_name != desired_name:
        text, applied = csv_io.set_column(text, symbol, _NAME_COL, desired_name)
        if applied:
            changed.append("name")

    if current_desc != desired_desc:
        text, applied = csv_io.set_column(text, symbol, _DESC_COL, desired_desc)
        if applied:
            changed.append("description")

    if not changed:
        return text  # already matches — no churn, no report line

    report.add(ReportEntry(
        status="applied", category="ability", chrooked_id=chrooked_id, symbol=symbol,
        reason="retuned: " + ", ".join(changed),
    ))
    return text


def _create_row(
    text: str,
    ability: AbilityDef,
    internal: str,
    report: ApplyReport,
    chrooked_id: str,
) -> str:
    """Append a new abilities.txt row at max_index + 1."""
    columns = [""] * _ROW_WIDTH
    columns[_IDX_COL] = str(csv_io.max_index(text) + 1)
    columns[_INTERNAL_COL] = internal
    columns[_NAME_COL] = ability.name
    columns[_DESC_COL] = _quote_desc(ability.description)

    text = csv_io.append_row(text, csv_io.join_columns(columns))
    # Plugin-aware boundary (#16): if a port exists it will be INSTALLED by the
    # behaviors tier, so this is not DATA-ONLY; otherwise keep the honest warning.
    if behavior_install.has_plugin(chrooked_id):
        reason = f"created new ability; mechanic installed via Scripts/chrooked_{chrooked_id}.rb"
    else:
        reason = "created new ability — DATA ONLY; mechanic must be implemented in the target engine"
    report.add(ReportEntry(
        status="applied", category="ability", chrooked_id=chrooked_id, symbol=internal,
        reason=reason,
    ))
    return text


def _internal_of(ability: AbilityDef) -> str:
    """Resolve the INTERNAL name for an ability: aka hint first, then vocab derivation."""
    hint = (ability.aka or {}).get("essentials")
    return str(hint) if hint else vocab.internal_name(ability.name)


def _quote_desc(description: str) -> str:
    """Ensure the description is double-quoted, as required by the 16.2 abilities.txt format."""
    if description.startswith('"') and description.endswith('"') and len(description) >= 2:
        return description
    return '"' + description + '"'
