"""Bake the form-sprite-id map the frontend uses to show form sprites.

The base snapshot stores every form under its shared *national* dex number
(Hisuian Goodra is 706, same as Goodra), so a sprite-by-dex URL can only ever
show the base form. PokeAPI does carry a distinct sprite per form, keyed by a
separate numeric id (Hisuian Goodra is 10242). This script resolves each form's
`chrooked_id` to that PokeAPI form id by matching the display name against
PokeAPI's `/pokemon` list, and writes `frontend/src/data/sprite-ids.json`.

Run it only when the base snapshot's species set changes (a new 1.11.2 pin).
It needs network access. Forms PokeAPI doesn't model with a distinct sprite
(Alcremie decoration combos, some Paldean Tauros) are intentionally omitted —
the frontend falls back to the base dex sprite for anything not in the map.

    python scripts/build_sprite_index.py
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from chrooked_pokedex.web import snapshot as snapmod

POKEAPI_LIST = "https://pokeapi.co/api/v2/pokemon?limit=20000"
_DATA_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data"
OUT = _DATA_DIR / "sprite-ids.json"
NATIONAL_OUT = _DATA_DIR / "national-dex.json"


def _fetch_name_index() -> dict[str, int]:
    request = urllib.request.Request(POKEAPI_LIST, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    index: dict[str, int] = {}
    for result in data["results"]:
        match = re.search(r"/pokemon/(\d+)/?$", result["url"])
        if match:
            index[result["name"]] = int(match.group(1))
    return index


def _pokeapi_slug(name: str) -> str:
    """Display name -> PokeAPI name slug: lowercase, punctuation dropped, spaces to hyphens."""
    cleaned = name.lower().replace("'", "").replace(".", "").replace(":", "")
    return re.sub(r"\s+", "-", cleaned.strip())


def build_map() -> dict[str, int]:
    index = _fetch_name_index()
    species = snapmod.load_snapshot()["species"]
    mapping: dict[str, int] = {}
    for chrooked_id, entry in species.items():
        if len(entry["name"].split()) < 2:
            continue  # single-word names are base forms; sprite-by-dex already works
        form_id = index.get(_pokeapi_slug(entry["name"]))
        # Keep only genuine form ids (a distinct sprite), not a base that happens
        # to match its own dex number.
        if form_id is not None and form_id != entry["dex"]:
            mapping[chrooked_id] = form_id
    return dict(sorted(mapping.items()))


def build_national_map() -> dict[str, int]:
    """chrooked_id -> canonical national dex №, offline from the base snapshot.

    The frontend CDN sprite resolver keys on national dex; a Target's own `dex`
    is local order and desyncs from national once it reorders the dex.
    """
    species = snapmod.load_snapshot()["species"]
    mapping = {cid: e["dex"] for cid, e in species.items() if e.get("dex")}
    return dict(sorted(mapping.items()))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    national = build_national_map()
    NATIONAL_OUT.write_text(json.dumps(national, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {NATIONAL_OUT} with {len(national)} national-dex entries.")

    mapping = build_map()
    OUT.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(mapping)} form-sprite entries.")


if __name__ == "__main__":
    main()
