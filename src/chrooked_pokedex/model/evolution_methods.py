"""The canonical, engine-neutral evolution-method vocabulary.

The Ruleset stores most evolutions as a clean `{level: N}` or `{item: X}` dict.
Everything else used to be carried only as a raw per-engine hint
(`{pokeemerald: EVO_MOVE, param: MOVE_MIMIC}`), which leaks an engine token into
hand-edited content and applies to one engine only.

This module adds a small neutral layer: a finite set of canonical methods, each
mapping to one pokeemerald token and one Essentials token. A canonical method is
stored as `{method: <id>, param?: <value>}`. The three Appliers translate it via
`to_engine`; the web layer serves `public_list` so the editor's dropdown and the
table never drift. The long tail (~40 engine-specific methods) still rides the
raw hint, which `to_engine` deliberately leaves alone.

The model must not import the Appliers (layering: Appliers depend on the model,
never the reverse). So `to_engine` returns the engine token, the value kind, and
the *raw* param; each Applier applies its own symbol helper (`item_symbol`,
`internal_name`, a local `MOVE_` builder) per `value_kind`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class EvoMethod:
    """One canonical evolution method.

    `value_kind` is what kind of Value the method needs, which drives both the
    editor's adaptive Value field and how an Applier renders the param:
    `none` (no param), `level` (an integer), `item` (an item name), `move`
    (a move name), `map` (an engine-specific location id).
    """

    id: str
    label: str
    value_kind: str
    pokeemerald: str
    essentials: str


# Insertion order is display order (the editor dropdown and the endpoint follow
# it). Nine methods cover the real Ruleset; anything else is the raw escape.
CANONICAL: dict[str, EvoMethod] = {
    m.id: m
    for m in (
        EvoMethod("level", "Level", "level", "EVO_LEVEL", "Level"),
        EvoMethod("level_day", "Level (day)", "level", "EVO_LEVEL_DAY", "LevelDay"),
        EvoMethod("level_night", "Level (night)", "level", "EVO_LEVEL_NIGHT", "LevelNight"),
        EvoMethod("friendship", "Friendship", "none", "EVO_FRIENDSHIP", "Happiness"),
        EvoMethod("item", "Use item", "item", "EVO_ITEM", "Item"),
        EvoMethod("trade", "Trade", "none", "EVO_TRADE", "Trade"),
        EvoMethod("trade_item", "Trade w/ item", "item", "EVO_TRADE_ITEM", "TradeItem"),
        EvoMethod("knows_move", "Knows move", "move", "EVO_MOVE", "HasMove"),
        EvoMethod("location", "At location", "map", "EVO_MAPSEC", "Location"),
    )
}

# Reverse map: a raw engine token (either family) back to a canonical id. Used by
# the editor to seed its form from a backdrop's `method_detail.kind`.
_TOKEN_TO_ID: dict[str, str] = {}
for _m in CANONICAL.values():
    _TOKEN_TO_ID[_m.pokeemerald] = _m.id
    _TOKEN_TO_ID[_m.essentials] = _m.id


def to_engine(method: Mapping[str, object], engine: str) -> Optional[tuple[str, str, str]]:
    """Translate a canonical `{method: id, param?}` dict to one engine.

    Returns `(token, value_kind, raw_param)` for a canonical method, or `None`
    for a `{level}`/`{item}`/raw-hint dict — those are owned by the Applier's
    own branches. `engine` is `"pokeemerald"` or `"essentials"`. `raw_param` is
    the unconverted value; the Applier applies its own symbol helper.
    """
    mid = method.get("method")
    if not isinstance(mid, str):
        return None
    canonical = CANONICAL.get(mid)
    if canonical is None:
        return None
    token = canonical.pokeemerald if engine == "pokeemerald" else canonical.essentials
    raw_param = "" if "param" not in method else str(method["param"])
    return (token, canonical.value_kind, raw_param)


def id_for_token(token: str) -> Optional[str]:
    """A raw engine token (either family) → canonical id, or `None` if unknown."""
    return _TOKEN_TO_ID.get(token)


def public_list() -> list[dict]:
    """The endpoint payload: one object per canonical method, in display order."""
    return [
        {
            "id": m.id,
            "label": m.label,
            "value_kind": m.value_kind,
            "tokens": [m.pokeemerald, m.essentials],
        }
        for m in CANONICAL.values()
    ]
