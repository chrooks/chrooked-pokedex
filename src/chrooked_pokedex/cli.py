"""chrooked-pokedex command line.

Subcommands:

  seed   --fork PATH --base PATH [--ruleset DIR]
         Diff a fork against its base and (re)write the Ruleset YAML.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .seed.extractor import seed_from_fork
from .seed.writer import write_ruleset

_DEFAULT_RULESET = Path(__file__).resolve().parent.parent.parent / "ruleset"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chrooked-pokedex")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="Diff a fork against its base into the Ruleset.")
    seed.add_argument("--fork", required=True, type=Path, help="Path to the fork.")
    seed.add_argument("--base", required=True, type=Path, help="Path to the base.")
    seed.add_argument(
        "--ruleset",
        type=Path,
        default=_DEFAULT_RULESET,
        help="Ruleset folder to write (default: repo ruleset/).",
    )

    args = parser.parse_args(argv)
    if args.command == "seed":
        return _run_seed(args.fork, args.base, args.ruleset)
    parser.error(f"unknown command {args.command}")
    return 2


def _run_seed(fork: Path, base: Path, ruleset_dir: Path) -> int:
    _verify_base_version(base)
    data = seed_from_fork(fork, base)
    write_ruleset(data, ruleset_dir)

    counts = data.counts()
    print(f"Seeded Ruleset at {ruleset_dir}:")
    print(f"  species changed:       {counts['species_changed']}")
    print(f"  learnsets replaced:    {counts['learnsets_replaced']}")
    print(f"  moves owned:           {counts['moves_owned']}")
    print(f"  abilities owned:       {counts['abilities_owned']}")
    print(f"  type-chart overrides:  {counts['type_chart_overrides']}")
    return 0


def _verify_base_version(base: Path) -> None:
    """Guard against seeding from the wrong base. The seed must diff against the
    exact version Dreamstone forked from (1.11.2); a mismatched base would invent
    hundreds of phantom overrides for everything upstream changed."""
    version_file = base / "include" / "constants" / "expansion.h"
    if not version_file.exists():
        return
    text = version_file.read_text(encoding="utf-8")
    parts = {}
    for key in ("MAJOR", "MINOR", "PATCH"):
        for line in text.splitlines():
            token = f"EXPANSION_VERSION_{key}"
            if token in line:
                parts[key] = line.split()[-1].strip()
                break
    version = ".".join(parts.get(k, "?") for k in ("MAJOR", "MINOR", "PATCH"))
    if version != "1.11.2":
        print(
            f"WARNING: base reports version {version}, expected 1.11.2. "
            "Seeding against the wrong base fabricates phantom overrides.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
