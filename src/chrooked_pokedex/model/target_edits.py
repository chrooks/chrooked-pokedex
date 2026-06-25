"""Per-Target additive edits: layer a Target-only change on top of its own data.

A *Target Edit* is the additive sibling of a hold. A hold keeps the Target's data;
a Target Edit adds to it. This slice implements one flavor — additive learnset moves:
"teach this entity these moves, on this Target only" — without replacing the rest of
the Target's learnset.

Target Edits live at `ruleset/targets/<slug>/edits.yaml`, committed canon:

    learnset_add:
      - id: gothita
        moves:
          - { level: 1, move: Water Whip }

The motivating case: Africanvs's Gothita learns Water Whip that canonical Gothita
does not. An apply with no slug loads no edits, so behavior is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

import yaml


@dataclass(frozen=True)
class LearnsetAddition:
    """One move to append to a Target's learnset for an entity."""

    level: int
    move: str


@dataclass(frozen=True)
class TargetEdits:
    """Additive, Target-scoped edits layered on top of the Target's own data."""

    learnset_add: Mapping[str, tuple[LearnsetAddition, ...]] = field(default_factory=dict)

    def learnset_additions(self, chrooked_id: str) -> tuple[LearnsetAddition, ...]:
        """The moves to append to `chrooked_id`'s learnset on this Target."""
        return self.learnset_add.get(chrooked_id, ())


def load_target_edits(ruleset_dir: Path, slug: Optional[str]) -> TargetEdits:
    """Load `ruleset/targets/<slug>/edits.yaml`, or an empty TargetEdits.

    Returns empty when `slug` is None or the file is absent — both mean "no edits".
    Raises ValueError on a malformed addition (missing id/level/move).
    """
    if not slug:
        return TargetEdits()
    path = Path(ruleset_dir) / "targets" / slug / "edits.yaml"
    if not path.exists():
        return TargetEdits()

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a YAML mapping at the top level")

    learnset_add: dict[str, tuple[LearnsetAddition, ...]] = {}
    for entry in data.get("learnset_add") or []:
        chrooked_id = entry.get("id")
        if not chrooked_id:
            raise ValueError(f"{path.name}: a learnset_add entry is missing 'id'")
        additions: list[LearnsetAddition] = []
        for move_entry in entry.get("moves") or []:
            if "level" not in move_entry or "move" not in move_entry:
                raise ValueError(
                    f"{path.name}: a learnset_add move for {chrooked_id!r} "
                    f"needs both 'level' and 'move'"
                )
            additions.append(
                LearnsetAddition(level=int(move_entry["level"]), move=move_entry["move"])
            )
        learnset_add[chrooked_id] = tuple(additions)
    return TargetEdits(learnset_add=learnset_add)
