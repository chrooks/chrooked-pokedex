"""Bake the semantic-tag map the dex filters use (Legendary / Mythical / Starter).

The Ruleset and base snapshot carry no notion of "legendary" or "starter" — every
entry is just types/stats/abilities/learnset/evolution. The dex's semantic filters
need a tag source, so this bakes one into a committed frontend JSON keyed by
*national dex number* (a form inherits its species' tags: Galarian Articuno is
still legendary 144).

The sets are curated canonical national-dex numbers. PokeAPI exposes
`is_legendary` / `is_mythical` only per-species (1000+ requests), so a reviewed
constant set is the equivalent offline, deterministic source — easy to eyeball
and correct here. Starters have no API flag at all; the lines are listed by hand.

Run only when the species set or the franchise canon changes:

    python scripts/build_tags.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data" / "tags.json"

# National dex numbers. Gens 1-9. Edit + rerun to correct.
LEGENDARY: set[int] = {
    144, 145, 146, 150,  # Kanto birds + Mewtwo
    243, 244, 245, 249, 250,  # Johto beasts + tower duo
    377, 378, 379, 380, 381, 382, 383, 384,  # Hoenn regis, eon duo, weather trio
    480, 481, 482, 483, 484, 485, 486, 487, 488,  # Sinnoh lake trio, creation trio, etc.
    638, 639, 640, 641, 642, 643, 644, 645, 646,  # Unova musketeers, forces, tao trio
    716, 717, 718,  # Kalos
    772, 773, 785, 786, 787, 788, 789, 790, 791, 792, 800,  # Alola
    888, 889, 890, 891, 892, 894, 895, 896, 897, 898, 905,  # Galar + Hisui Enamorus
    1001, 1002, 1003, 1004, 1007, 1008, 1014, 1015, 1016, 1017, 1024,  # Paldea
}

MYTHICAL: set[int] = {
    151, 251, 385, 386, 489, 490, 491, 492, 493, 494,
    647, 648, 649, 719, 720, 721, 801, 802, 807, 808, 809, 893, 1025,
}

# First-stage national dex number of each starter line; the line is the next two.
_STARTER_LINE_STARTS = [
    1, 4, 7, 152, 155, 158, 252, 255, 258, 387, 390, 393,
    495, 498, 501, 650, 653, 656, 722, 725, 728, 810, 813, 816, 906, 909, 912,
]
STARTER: set[int] = {n for start in _STARTER_LINE_STARTS for n in (start, start + 1, start + 2)}

# Fossil Pokémon revived from fossils, plus their evolutions (whole lines).
FOSSIL: set[int] = {
    138, 139, 140, 141, 142,  # Kanto: Omanyte/Omastar, Kabuto/Kabutops, Aerodactyl
    345, 346, 347, 348,  # Hoenn: Lileep/Cradily, Anorith/Armaldo
    408, 409, 410, 411,  # Sinnoh: Cranidos/Rampardos, Shieldon/Bastiodon
    564, 565, 566, 567,  # Unova: Tirtouga/Carracosta, Archen/Archeops
    696, 697, 698, 699,  # Kalos: Tyrunt/Tyrantrum, Amaura/Aurorus
    880, 881, 882, 883,  # Galar: Dracozolt/Arctozolt, Dracovish/Arctovish
}

# Eevee and all of its evolutions.
EEVEE: set[int] = {
    133,  # Eevee
    134, 135, 136,  # Vaporeon, Jolteon, Flareon
    196, 197,  # Espeon, Umbreon
    470, 471,  # Leafeon, Glaceon
    700,  # Sylveon
}

# Pseudo-legendary lines (600-BST finals), tagged whole-line like the starters.
_PSEUDO_LINE_STARTS = [
    147,  # Dratini -> Dragonair -> Dragonite
    246,  # Larvitar -> Pupitar -> Tyranitar
    371,  # Bagon -> Shelgon -> Salamence
    374,  # Beldum -> Metang -> Metagross
    443,  # Gible -> Gabite -> Garchomp
    633,  # Deino -> Zweilous -> Hydreigon
    704,  # Goomy -> Sliggoo -> Goodra
    782,  # Jangmo-o -> Hakamo-o -> Kommo-o
    885,  # Dreepy -> Drakloak -> Dragapult
    996,  # Frigibax -> Arctibax -> Baxcalibur
]
PSEUDO_LEGENDARY: set[int] = {
    n for start in _PSEUDO_LINE_STARTS for n in (start, start + 1, start + 2)
}


def build_tags() -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    all_dex = LEGENDARY | MYTHICAL | STARTER | FOSSIL | EEVEE | PSEUDO_LEGENDARY
    for dex in sorted(all_dex):
        labels: list[str] = []
        if dex in LEGENDARY:
            labels.append("legendary")
        if dex in MYTHICAL:
            labels.append("mythical")
        if dex in STARTER:
            labels.append("starter")
        if dex in FOSSIL:
            labels.append("fossil")
        if dex in EEVEE:
            labels.append("eevee")
        if dex in PSEUDO_LEGENDARY:
            labels.append("pseudo")
        tags[str(dex)] = labels
    return tags


def main() -> None:
    tags = build_tags()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(tags, indent=0) + "\n", encoding="utf-8")
    counts = {
        "legendary": len(LEGENDARY),
        "mythical": len(MYTHICAL),
        "starter": len(STARTER),
        "fossil": len(FOSSIL),
        "eevee": len(EEVEE),
        "pseudo": len(PSEUDO_LEGENDARY),
    }
    print(f"Wrote {OUT} with {len(tags)} tagged dex numbers. {counts}")


if __name__ == "__main__":
    main()
