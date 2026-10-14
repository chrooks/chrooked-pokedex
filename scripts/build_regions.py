"""Bake the regional-dex membership map the dex's Regional Dex filter uses.

Keyed by *national dex number* (string) -> the regions whose Pokédex lists that
species. Each region is the union of every game dex for it (Sinnoh = DP +
Platinum, Galar = base + Isle of Armor + Crown Tundra), because "fits in the
Sinnoh dex" means any Sinnoh game. A form inherits its species' row.

Origin region is NOT here: it derives from the dex-number range plus the form
name in the frontend (dexRegions.ts), no data needed.

Source: PokeAPI pokedex endpoints (one request per game dex, ~25 total). Run
only when the franchise canon changes:

    python scripts/build_regions.py
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data" / "regions.json"
API = "https://pokeapi.co/api/v2/pokedex/"

# Region label -> the PokeAPI pokedex slugs that count as that region's dex.
REGION_DEXES: dict[str, list[str]] = {
    "Kanto": ["kanto", "letsgo-kanto"],
    "Johto": ["original-johto", "updated-johto"],
    "Hoenn": ["hoenn", "updated-hoenn"],
    "Sinnoh": ["original-sinnoh", "extended-sinnoh"],
    "Unova": ["original-unova", "updated-unova"],
    "Kalos": ["kalos-central", "kalos-coastal", "kalos-mountain"],
    "Alola": ["original-alola", "updated-alola"],
    "Galar": ["galar", "isle-of-armor", "crown-tundra"],
    "Hisui": ["hisui"],
    "Paldea": ["paldea", "kitakami", "blueberry"],
}


def fetch_dex_numbers(slug: str) -> set[int]:
    # PokeAPI 403s the default urllib User-Agent.
    req = urllib.request.Request(API + slug, headers={"User-Agent": "chrooked-pokedex"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    # The species URL ends in /pokemon-species/<national dex>/.
    return {
        int(entry["pokemon_species"]["url"].rstrip("/").rsplit("/", 1)[1])
        for entry in data["pokemon_entries"]
    }


def build_regions() -> dict[str, list[str]]:
    by_dex: dict[int, list[str]] = {}
    for region, slugs in REGION_DEXES.items():
        members: set[int] = set()
        for slug in slugs:
            members |= fetch_dex_numbers(slug)
        for dex in members:
            by_dex.setdefault(dex, []).append(region)
        print(f"{region}: {len(members)}")
    return {str(dex): regions for dex, regions in sorted(by_dex.items())}


def main() -> None:
    regions = build_regions()
    OUT.write_text(json.dumps(regions, indent=0) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(regions)} dex numbers.")


if __name__ == "__main__":
    main()
