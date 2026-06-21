"""The Essentials-flavored evolution method labeler.

Sibling to ``web/evolution.method_label``, but for the Essentials PBS method
vocabulary (``Level``/``Item``/``HappinessDay``/…) rather than the pokeemerald
``EVO_*`` one. Injected into ``build_evolution_graph`` via its ``labeler`` Seam
so one shared invert+resolve transform serves both engines.

The honesty mirrors the write path (``appliers/essentials/evolution_apply``):
clean-label the two common methods (``Level`` -> "Level N", ``Item`` -> the
humanized item name), and humanize any other method token, appending its param
only when it carries meaning. No edge ever renders a raw token.
"""

from __future__ import annotations


def essentials_method_label(method: str, param: str) -> str:
    """A human-readable evolution method from an Essentials `(method, param)` pair.

    Examples:

    - `Level` / `16`            -> "Level 16"
    - `Item`  / `WATERSTONE`    -> "Water Stone"
    - `HappinessDay` / anything -> "Happiness Day"
    - `Trade` / `0`             -> "Trade" (sentinel param dropped)
    """
    if method == "Level" and param.isdigit():
        return f"Level {param}"
    if method == "Item":
        return _humanize_item(param)
    label = _humanize_token(method)
    if param and param != "0":
        piece = param if param.isdigit() else _humanize_token(param)
        return f"{label} {piece}"
    return label


# Item internal names are joined all-caps (``WATERSTONE``) with no separator to
# split on. These common evolution-item suffixes are peeled so the label reads
# as two words (``WATERSTONE`` -> "Water Stone") instead of "Waterstone".
_ITEM_SUFFIXES = ("STONE",)


def _humanize_item(token: str) -> str:
    """`WATERSTONE` -> "Water Stone"; falls back to plain humanization.

    Essentials item internal names are joined all-caps, so a known suffix
    (``STONE``) is split off the end before title-casing. A token carrying its
    own separators (underscore / camelCase) flows through plain humanization.
    """
    if "_" not in token and not any(c.islower() for c in token):
        for suffix in _ITEM_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix):
                stem = token[: -len(suffix)]
                return f"{stem.title()} {suffix.title()}"
    return _humanize_token(token)


def _humanize_token(token: str) -> str:
    """`WATERSTONE` / `HappinessDay` / `MAP_NAME` -> Title-cased words.

    Splits on underscores and camelCase boundaries, then title-cases. A bare
    all-caps token with no separators (``WATERSTONE``) is treated as a single
    word and title-cased to "Waterstone"; common item names like ``WATERSTONE``
    read fine that way, and there is no dictionary to split joined words.
    """
    spaced: list[str] = []
    previous = ""
    for char in token.replace("_", " "):
        if char.isupper() and previous and previous.islower():
            spaced.append(" ")
        spaced.append(char)
        previous = char
    return "".join(spaced).replace("  ", " ").strip().title()
