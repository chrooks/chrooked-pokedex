"""Overlay species types and base stats onto ROM records, one Block per species.

The ROM is the baseline: read the record, change only the overridden fields,
keep every other byte. Field offsets always come from the Addresses file.
"""

from __future__ import annotations

from typing import BinaryIO

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from .addresses import ROM_BUS_BASE, Addresses
from .blocks import Block
from .resolution import ResolutionMap

_STATS = ("hp", "atk", "def", "spa", "spd", "spe")
_MAX_BYTE = 255


def _blocked(cid: str, reason: str, symbol: str | None = None) -> ReportEntry:
    return ReportEntry("blocked", "species", cid, symbol=symbol, reason=reason)


def apply_species(
    rom: BinaryIO,
    ruleset: Ruleset,
    resmap: ResolutionMap,
    addresses: Addresses,
    report: ApplyReport,
) -> list[Block]:
    table = addresses.tables["base_stats"]
    fields = table.fields
    blocks: list[Block] = []
    for cid, species in sorted(ruleset.species.items()):
        if not species.types and not species.stats:
            continue  # nothing this slice can write (e.g. learnset-only)
        index = resmap.species(species.aka, species.name)
        if index is None:
            report.add(_blocked(
                cid,
                f"no Monomyth species named '{species.name}'; "
                "add aka: {monomyth: <index>} or leave it",
            ))
            continue
        symbol = f"#{index} {resmap.species_names[index]}"
        address = table.address + index * table.stride
        rom.seek(address - ROM_BUS_BASE)
        original = rom.read(table.stride)
        if len(original) != table.stride:
            report.add(_blocked(cid, f"record at 0x{address:08X} runs past the end of the ROM", symbol))
            continue

        stats = dict(species.stats or {})
        bad = {k: v for k, v in stats.items() if k in _STATS and not 0 <= v <= _MAX_BYTE}
        if bad:
            report.add(_blocked(cid, f"Gen 3 base stats are one byte (0-255): {bad}", symbol))
            continue

        record = bytearray(original)
        written: list[str] = []
        partial: list[str] = []
        for key in _STATS:
            if key in stats and key in fields:
                record[fields[key]] = stats[key]
                written.append(key)
            elif key in stats:
                partial.append(f"stats.{key}")
        if species.types:
            ids = [resmap.type_id(t) for t in species.types]
            if None in ids or len(ids) > 2 or not {"type1", "type2"} <= fields.keys():
                partial.append("types")
            else:
                # A one-type species stores the same id twice, as Gen 3 does.
                record[fields["type1"]] = ids[0]
                record[fields["type2"]] = ids[-1]
                written.append("types")

        patched = bytes(record)
        if patched != original:
            blocks.append(Block(address, original, patched))
            reason = f"wrote {', '.join(written)}"
        else:
            reason = "already matches" if written else "nothing written"
        if partial:
            report.add(ReportEntry(
                "partial", "species", cid, symbol=symbol,
                reason=f"{reason}; could not write {', '.join(partial)}",
                partial_fields=tuple(partial),
            ))
        else:
            report.add(ReportEntry("applied", "species", cid, symbol=symbol, reason=reason))
    return blocks
