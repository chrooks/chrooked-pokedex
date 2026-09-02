"""Ability-driven power multipliers, for BAND PLACEMENT only.

Sharpness makes a 90 BP cut land as 117, so a species carrying it must pace its
slicing rungs against the boosted number. Without this, a ladder reads a cut as
a mid-game rung when it is really a late one, and the pacing audit reports a
gap in a bracket the boosted moves already fill (Gallade, 2026-09-02).

This is editorial arithmetic, not battle maths — real damage is the engine's
business. Nothing here changes what a move does; it only changes which bracket
a banding pass thinks it belongs in.

Keyed on chrooked_id so a display name never has to be spelled twice.
"""

from __future__ import annotations

from typing import Iterable, Mapping

# chrooked_id -> (move flag it boosts, multiplier).
#
# Only NARROW flag classes belong here. `contact` is deliberately absent even
# though Tough Claws boosts it: contact covers most of the physical pool, so
# banding against it would shift nearly every physical ladder rather than
# correcting a coverage class. Add one only when a real species uses it and the
# flag names a genuine move family.
ABILITY_POWER_MODS: Mapping[str, tuple[str, float]] = {
    "sharpness": ("slicing", 1.3),
    "mysticblades": ("slicing", 1.3),
    "strongjaw": ("biting", 1.5),
    "apexpredator": ("biting", 1.5),   # composes strongjaw + carnivore
    "infernalmaw": ("biting", 1.3),
    "ironfist": ("punching", 1.2),
    "megalauncher": ("pulse", 1.5),
}


def _key(name: str) -> str:
    """Display name or chrooked_id -> chrooked_id ('Strong Jaw' -> 'strongjaw')."""
    return "".join(ch for ch in name.lower() if ch.isalnum())


def power_multiplier(abilities: Iterable[str], flags: Iterable[str]) -> float:
    """Banding multiplier for one move on a species carrying `abilities`.

    Returns 1.0 when nothing applies. When several abilities boost the same
    move the LARGEST wins rather than the product — a species never has two of
    these live on one move in practice, and stacking them would overstate the
    bracket. Under Redux Mode all three slots are live at once, which is why
    every slot is read, not just the primary.
    """
    owned = {_key(a) for a in abilities if a}
    flagset = set(flags or ())
    best = 1.0
    for ability in owned:
        mod = ABILITY_POWER_MODS.get(ability)
        if mod and mod[0] in flagset:
            best = max(best, mod[1])
    return best


def slots(abilities: Mapping[str, str] | None) -> tuple[str, ...]:
    """The ability names in a species' three slots, empties dropped."""
    if not abilities:
        return ()
    return tuple(
        v for v in (abilities.get(k) for k in ("primary", "secondary", "hidden")) if v
    )


def demo() -> None:
    """Self-check: the cases that motivated this module."""
    assert power_multiplier(["Sharpness"], ["contact", "slicing"]) == 1.3
    assert power_multiplier(["Sharpness"], ["contact"]) == 1.0
    assert power_multiplier(["Apex Predator"], ["biting"]) == 1.5
    assert power_multiplier(["apexpredator"], ["biting"]) == 1.5, "id form too"
    assert power_multiplier(["Levitate", "Magic Guard"], ["slicing"]) == 1.0
    # Largest wins, never the product.
    assert power_multiplier(["Strong Jaw", "Infernal Maw"], ["biting"]) == 1.5
    assert power_multiplier([], ["slicing"]) == 1.0
    assert slots({"primary": "Sharpness", "secondary": None, "hidden": "Justified"}) == (
        "Sharpness", "Justified",
    )
    assert slots(None) == ()
    # The two real cases: Gallade's Cross Chop and Luxray's Thunder Fang.
    assert round(100 * power_multiplier(["Sharpness"], ["contact", "slicing"])) == 130
    assert round(80 * power_multiplier(["Apex Predator"], ["contact", "biting"])) == 120
    print("power_mods: ok")


if __name__ == "__main__":
    demo()
