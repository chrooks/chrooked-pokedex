"""The Rejuvenation Resolution map: neutral identity -> Ruby symbol / form.

Rejuv's internal names are UPPERCASE, no separators (``:POISONHEAL``,
``:XSCISSOR``), which is exactly ``slug(name).upper()``. So resolution is: slug
the neutral name, uppercase it, and confirm the symbol actually exists in the
scanned base file. A name the target genuinely lacks resolves to ``None`` and is
surfaced in the Apply Report — never fabricated.

Species carry an extra wrinkle: forms. A ``chrooked_id`` maps to a
``(MONHASH key, form name)`` pair; the default form is ``"Normal Form"``. Megas
are stored as a ``"Mega Form"`` sub-key under the base species (not a separate
top-level key), so a ``*mega`` id is retried against the base species + Mega
Form. Anything still unresolved (multi-mega, regional variants) blocks unless an
``aka.rejuv`` hint pins it explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from ...seed.neutralize import slug
from . import definitions_read

_DEFAULT_FORM = "Normal Form"


@dataclass
class RejuvResolution:
    """Neutral identity -> Rejuv symbols, for one target's base definition files."""

    monhash: dict[str, list[str]]      # species key -> form names
    move_syms: set[str]
    ability_syms: set[str]
    max_ability_id: int                # highest :ID in the base abiltext (for new abilities)

    @classmethod
    def build(cls, target: Path) -> "RejuvResolution":
        defs = target / "Scripts" / "Rejuv" / "Definitions"
        return cls(
            monhash=definitions_read.scan_monhash_keys(defs / "montext.rb"),
            move_syms=definitions_read.scan_symbol_keys(defs / "movetext.rb"),
            ability_syms=definitions_read.scan_symbol_keys(defs / "abiltext.rb"),
            max_ability_id=definitions_read.max_ability_id(defs / "abiltext.rb"),
        )

    def species(self, chrooked_id: str, aka: Mapping[str, object]) -> Optional[tuple[str, str]]:
        """Resolve to ``(MONHASH key, form name)`` or None."""
        hint = aka.get("rejuv") if aka else None
        if isinstance(hint, str) and hint:
            # "KEY" or "KEY::Form Name"
            key, _, form = hint.partition("::")
            form = form or _DEFAULT_FORM
            if key in self.monhash and form in self.monhash[key]:
                return (key, form)
            return None

        upper = slug(chrooked_id).upper()
        if upper in self.monhash and _DEFAULT_FORM in self.monhash[upper]:
            return (upper, _DEFAULT_FORM)

        # ponytail: cheap mega heuristic — "<base>mega" -> (BASE, "Mega Form").
        # Covers the ~48 single-mega species; multi-megas (charizardmegax) and
        # regionals still block and can be rescued with an aka.rejuv hint.
        if upper.endswith("MEGA"):
            base = upper[:-4]
            if base in self.monhash and "Mega Form" in self.monhash[base]:
                return (base, "Mega Form")
        return None

    def move(self, name: str) -> Optional[str]:
        sym = slug(name).upper()
        return sym if sym in self.move_syms else None

    def ability(self, name: str) -> Optional[str]:
        sym = slug(name).upper()
        return sym if sym in self.ability_syms else None

    def ability_symbol(self, name: str) -> str:
        """The symbol a name WOULD take, whether or not it exists yet (for new abilities)."""
        return slug(name).upper()
