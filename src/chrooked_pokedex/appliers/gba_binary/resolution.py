"""The gba-binary Resolution map: aka hint / display name -> species index.

Exact (case-insensitive) name match only — a near miss would write one
creature's stats onto another with no signal. A miss is a blocked report row
and an `aka: {monomyth: <index>}` hint fixes it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Optional

from .addresses import Addresses


@dataclass(frozen=True)
class ResolutionMap:
    name_to_index: Mapping[str, int]
    types: Mapping[str, int]
    species_count: int
    species_names: tuple[str, ...] = ()

    def species(self, aka: Mapping[str, object], name: str) -> Optional[int]:
        hint = (aka or {}).get("monomyth")
        if hint is not None:
            # Out of range (or not an int) -> None, so the caller reports blocked
            # instead of reading/writing past the table. Index 0 is the blank slot.
            is_index = isinstance(hint, int) and not isinstance(hint, bool)
            return hint if is_index and 0 < hint < self.species_count else None
        return self.name_to_index.get(name.casefold())

    def type_id(self, name: str) -> Optional[int]:
        return self.types.get(name.casefold())


def build_resolution_map(addresses: Addresses) -> ResolutionMap:
    names = addresses.species_names
    folded = [n.casefold() for n in names]
    counts = Counter(folded[1:])
    # A name shared by two indexes is ambiguous: leave it unmatched (aka fixes it).
    name_to_index = {n: i for i, n in enumerate(folded) if i > 0 and counts[n] == 1}
    return ResolutionMap(
        name_to_index=name_to_index,
        types={t.casefold(): i for i, t in enumerate(addresses.types)},
        species_count=len(names),
        species_names=names,
    )
