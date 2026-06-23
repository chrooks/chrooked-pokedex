"""Read Essentials 16.2 alt-form sections from `pokemonforms.txt`.

Unlike `pokemon.txt` — numeric `[N]` headers whose identity lives in `InternalName=` —
the forms file keys each section by a `[BASE-N]` header (BASE is the base species'
InternalName, N the form index) and carries NO `InternalName`. A form's identity is its
`FormName=` field ("Mega Kangaskhan", "Attack Forme", "Summer Form").

This reader is read-only; edits go through `forms_edit`, which preserves the bytes
around a change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A `[BASE-N]` header line. Sibling of `forms_edit._HEADER_LINE`. BASE is an
# InternalName (letters/digits/underscore); N is the form index.
_HEADER = re.compile(r"^\[[ \t]*([A-Za-z0-9_]+)-(\d+)[ \t]*\][ \t]*$")


@dataclass(frozen=True)
class FormSection:
    """One `[BASE-N]` form section: its header, base internal, index, and FormName."""

    header: str       # the literal inside-bracket string, e.g. "DEOXYS-1"
    base: str         # the base species InternalName, e.g. "DEOXYS"
    index: int        # the form index N
    form_name: str | None  # the FormName= value, or None when absent


def parse_form_sections(text: str) -> list[FormSection]:
    """Return every `[BASE-N]` form section in file order.

    Lines are split on the first `=`; blank lines and `#` comments are skipped. A
    section with no `FormName=` keeps `form_name=None` (it still has a stable header).
    """
    sections: list[FormSection] = []
    header: str | None = None
    base = ""
    index = 0
    form_name: str | None = None

    def flush() -> None:
        if header is not None:
            sections.append(FormSection(header, base, index, form_name))

    for line in text.split("\n"):
        line = line.rstrip("\r")
        match = _HEADER.match(line)
        if match:
            flush()
            base, index_str = match.group(1), match.group(2)
            header = f"{base}-{index_str}"
            index = int(index_str)
            form_name = None
            continue
        if header is None:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == "FormName" and form_name is None:
            form_name = value.strip()
    flush()
    return sections
