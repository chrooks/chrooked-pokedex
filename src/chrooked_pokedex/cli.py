"""chrooked-pokedex command line.

Subcommands:

  seed   --fork PATH --base PATH [--ruleset DIR]
         Diff a fork against its base and (re)write the Ruleset YAML.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .appliers.pokeemerald.git_guard import DirtyWorkingTree, require_clean_git_status
from .appliers.pokeemerald.resolution import build_resolution_map
from .appliers.pokeemerald.species_apply import apply_species
from .model import Ruleset
from .report import ApplyReport
from .seed.extractor import seed_from_fork
from .seed.writer import write_ruleset

_DEFAULT_RULESET = Path(__file__).resolve().parent.parent.parent / "ruleset"
_APPLY_CATEGORIES = ("species",)


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

    apply = sub.add_parser("apply", help="Write the Ruleset into a target fork.")
    apply.add_argument("--target", required=True, type=Path, help="Path to the fork.")
    apply.add_argument(
        "--category",
        choices=(*_APPLY_CATEGORIES, "all"),
        default="all",
        help="Which category to apply (default: all).",
    )
    apply.add_argument(
        "--ruleset", type=Path, default=_DEFAULT_RULESET, help="Ruleset folder to read."
    )
    apply.add_argument(
        "--force", action="store_true", help="Apply even if the target git tree is dirty."
    )

    args = parser.parse_args(argv)
    if args.command == "seed":
        return _run_seed(args.fork, args.base, args.ruleset)
    if args.command == "apply":
        return _run_apply(args.target, args.category, args.ruleset, args.force)
    parser.error(f"unknown command {args.command}")
    return 2


def _run_apply(target: Path, category: str, ruleset_dir: Path, force: bool) -> int:
    try:
        require_clean_git_status(target, force=force)
    except DirtyWorkingTree as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    ruleset = Ruleset.load(ruleset_dir)
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    categories = _APPLY_CATEGORIES if category == "all" else (category,)
    if "species" in categories:
        changed = apply_species(target, ruleset, resmap, report)
        print(f"species: {len(changed)} file(s) changed")

    json_path = report.write(target / "apply-report.md")
    counts = report.counts()
    print(
        f"Apply Report: applied={counts['applied']} "
        f"partial={counts['partial']} blocked={counts['blocked']}"
    )
    print(f"  {target / 'apply-report.md'}")
    print(f"  {json_path}")
    return 0


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
