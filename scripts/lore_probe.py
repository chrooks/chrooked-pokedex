#!/usr/bin/env python3
"""Print the lore block a species would get injected into its suggest prompt.

The one command that proves the fetch works against the real internet, since the
test suite is deliberately hermetic. Milestone 1 of issue #75.

    .venv/bin/python scripts/lore_probe.py glalie
    .venv/bin/python scripts/lore_probe.py marowakalola   # form -> base mapping
    .venv/bin/python scripts/lore_probe.py palossandicyaevian  # the not-found path

Results are cached under .cache/lore/, so a second run is offline and instant.
Delete a species' file there to refetch it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chrooked_pokedex.web.lore import HttpLoreProvider, LoreError  # noqa: E402
from chrooked_pokedex.web.lore_text import DEFAULT_LORE_CAP, render_lore  # noqa: E402
from chrooked_pokedex.web.snapshot import (  # noqa: E402
    DEFAULT_SNAPSHOT_PATH,
    load_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chrooked_id", help="species id, e.g. glalie")
    parser.add_argument(
        "--cap",
        type=int,
        default=DEFAULT_LORE_CAP,
        help=f"character cap on the rendered block (default {DEFAULT_LORE_CAP})",
    )
    args = parser.parse_args()

    snapshot = load_snapshot(DEFAULT_SNAPSHOT_PATH)
    species = snapshot.get("species", {})
    entry = species.get(args.chrooked_id) or {}
    name = entry.get("name") or args.chrooked_id.capitalize()

    provider = HttpLoreProvider(known_species=species.keys())
    try:
        result = provider.fetch(args.chrooked_id, name)
    except LoreError as error:
        print(f"LORE FETCH FAILED: {error}", file=sys.stderr)
        return 1

    print(f"=== {name} ({args.chrooked_id}) ===")
    print(f"found        : {result.found}")
    print(f"base species : {result.base_species}")
    print(f"sources      : {', '.join(result.sources) or '(none)'}")
    print(f"raw chars    : {result.chars}")
    print()
    block = render_lore(
        found=result.found,
        genus=result.genus,
        dex_entries=result.dex_entries,
        origin=result.origin,
        name_origin=result.name_origin,
        requested_id=args.chrooked_id,
        base_species=result.base_species,
        cap=args.cap,
    )
    print(block)
    print()
    print(f"--- injected block: {len(block)} chars (cap {args.cap}) ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
