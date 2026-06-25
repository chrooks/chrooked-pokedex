"""Per-Target holds: keep a Target's own version of a category, Ruleset stands down.

A *hold* is the subtractive mirror of an Override. Where an Override changes a field
for every Target, a hold names a `chrooked_id` and the categories the Ruleset must
*not* write for one Target — so that Target's own data (a regional form already in its
files) survives an apply untouched.

Holds live at `ruleset/targets/<slug>/holds.yaml`, committed canon:

    holds:
      - id: gothita
        categories: [species, abilities, learnset]

An apply with no slug (`--as` omitted) loads no holds, so behavior is unchanged.
A typo'd category is a load-time error, not a silent no-op — a hold that fails to
hold would clobber the Target's data without warning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

import yaml

# The categories a hold may name. These mirror the Appliers' write tiers; a hold
# suppresses one tier's write for one entity. Engine-neutral: every engine applies
# some subset of these, and naming one an engine does not write is harmless.
HOLDABLE_CATEGORIES: frozenset[str] = frozenset(
    {"abilities", "moves", "species", "learnset", "evolution", "type-chart", "behaviors"}
)


@dataclass(frozen=True)
class HoldSet:
    """Which (chrooked_id, category) pairs a Target keeps as its own."""

    held: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def is_held(self, chrooked_id: str, category: str) -> bool:
        """True when the Ruleset must NOT write `category` for `chrooked_id`."""
        return category in self.held.get(chrooked_id, frozenset())


def load_holds(ruleset_dir: Path, slug: Optional[str]) -> HoldSet:
    """Load `ruleset/targets/<slug>/holds.yaml`, or an empty HoldSet.

    Returns empty when `slug` is None (no `--as` given) or the file is absent —
    both mean "nothing held", today's behavior. Validates every category name
    against `HOLDABLE_CATEGORIES` and raises ValueError on an unknown one.
    """
    if not slug:
        return HoldSet()
    path = Path(ruleset_dir) / "targets" / slug / "holds.yaml"
    if not path.exists():
        return HoldSet()

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a YAML mapping at the top level")

    held: dict[str, frozenset[str]] = {}
    for entry in data.get("holds") or []:
        chrooked_id = entry.get("id")
        if not chrooked_id:
            raise ValueError(f"{path.name}: a holds entry is missing 'id'")
        categories = tuple(entry.get("categories") or ())
        unknown = [c for c in categories if c not in HOLDABLE_CATEGORIES]
        if unknown:
            raise ValueError(
                f"{path.name}: unknown hold category(ies) {', '.join(sorted(unknown))} "
                f"for {chrooked_id!r}; allowed are {', '.join(sorted(HOLDABLE_CATEGORIES))}"
            )
        held[chrooked_id] = frozenset(categories)
    return HoldSet(held=held)
