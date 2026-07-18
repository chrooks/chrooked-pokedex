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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from ...seed.neutralize import slug
from . import definitions_read

_DEFAULT_FORM = "Normal Form"
# Generic form words stripped when computing a form's "core" for exact matching.
_FORM_WORDS = ("forme", "form", "mode")


def _form_core(form_name: str) -> str:
    """The distinguishing slug of a form name, minus generic words.

    "Mega Form" -> "mega", "Mega X Form" -> "megax", "Standard Mode" -> "standard".
    """
    from ...seed.neutralize import slug as _slug
    core = form_name.lower()
    for word in _FORM_WORDS:
        core = core.replace(word, " ")
    return _slug(core)


@dataclass
class RejuvResolution:
    """Neutral identity -> Rejuv symbols, for one target's base definition files."""

    monhash: dict[str, list[str]]      # species key -> form names
    move_syms: set[str]
    ability_syms: set[str]
    max_ability_id: int                # highest :ID in the base abiltext (for new abilities)
    max_move_id: int                   # highest :ID in the base movetext (for new moves)
    move_names: dict[str, str] = field(default_factory=dict)     # slug(display) -> symbol
    ability_names: dict[str, str] = field(default_factory=dict)  # slug(display) -> symbol

    @classmethod
    def build(cls, target: Path) -> "RejuvResolution":
        defs = target / "Scripts" / "Rejuv" / "Definitions"
        return cls(
            monhash=definitions_read.scan_monhash_keys(defs / "montext.rb"),
            move_syms=definitions_read.scan_symbol_keys(defs / "movetext.rb"),
            ability_syms=definitions_read.scan_symbol_keys(defs / "abiltext.rb"),
            max_ability_id=definitions_read.max_ability_id(defs / "abiltext.rb"),
            max_move_id=definitions_read.max_move_id(defs / "movetext.rb"),
            move_names=definitions_read.scan_symbol_names(defs / "movetext.rb"),
            ability_names=definitions_read.scan_symbol_names(defs / "abiltext.rb"),
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

        return self._match_form(upper)

    def _match_form(self, upper: str) -> Optional[tuple[str, str]]:
        """Rescue a form/mega/regional id by matching its suffix to a form name.

        Take the longest MONHASH key that prefixes the id, slug its remaining
        suffix, and find forms whose slug CONTAINS that suffix slug. Resolve only
        when exactly one form matches — an ambiguous or zero match stays blocked
        rather than risk writing to the wrong form. Rejuv form spellings are
        irregular ("Mega X Form", "Shield Forme", "Red-Striped", "Hisuian Form"),
        so slug-substring beats any fixed suffix rule; the single-match guard keeps
        it safe. Subsumes the old mega heuristic (suffix "megax" -> "Mega X Form").
        """
        prefixes = [k for k in self.monhash if upper.startswith(k)]
        if not prefixes:
            return None
        key = max(prefixes, key=len)
        suffix = slug(upper[len(key):])
        if not suffix:
            return (key, self.monhash[key][0])  # bare species, non-default first form
        # Tier 1: exact form-core match — the form's name minus generic words
        # ("Form"/"Forme"/"Mode") equals the suffix. This resolves "mega" to the
        # plain "Mega Form" even when a "Mega Form Z" also exists, and rescues
        # "standard" -> "Standard Mode".
        exact = [f for f in self.monhash[key] if _form_core(f) == suffix]
        if len(exact) == 1:
            return (key, exact[0])
        # Tier 2: unambiguous substring — resolve only on a single match.
        forms = [f for f in self.monhash[key] if suffix in slug(f)]
        return (key, forms[0]) if len(forms) == 1 else None

    def move(self, name: str) -> Optional[str]:
        sym = slug(name).upper()
        if sym in self.move_syms:
            return sym
        return self.move_names.get(slug(name))  # name index (VICEGRIP/"Vise Grip")

    def move_symbol(self, name: str) -> str:
        """The existing symbol for this move, or the symbol a new move WOULD take."""
        return self.move(name) or slug(name).upper()

    def ability(self, name: str) -> Optional[str]:
        sym = slug(name).upper()
        if sym in self.ability_syms:
            return sym
        return self.ability_names.get(slug(name))

    def ability_symbol(self, name: str) -> str:
        """The existing symbol for this ability, or the symbol a new one WOULD take."""
        return self.ability(name) or slug(name).upper()
