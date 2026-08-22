"""chrooked-pokedex command line.

Subcommands:

  seed   --fork PATH --base PATH [--ruleset DIR]
         Diff a fork against its base and (re)write the Ruleset YAML.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .appliers.essentials import (
    creation as essentials_creation,
    evolution_apply as essentials_evolution,
    learnset_apply as essentials_learnset,
    move_apply as essentials_moves,
    resolution as essentials_resolution,
    species_apply as essentials_species,
    type_chart_apply as essentials_type_chart,
)
from .appliers.essentials162 import (
    ability_apply as essentials162_abilities,
    behavior_install as essentials162_behaviors,
    evolution_apply as essentials162_evolution,
    forms_apply as essentials162_forms,
    learnset_apply as essentials162_learnset,
    move_apply as essentials162_moves,
    resolution as essentials162_resolution,
    species_apply as essentials162_species,
    type_chart_apply as essentials162_type_chart,
)
from .appliers.pokeemerald.creation import create_owned_content
from .appliers.pokeemerald.evolution_apply import apply_evolutions
from .appliers.pokeemerald.git_guard import DirtyWorkingTree, require_clean_git_status
from .appliers.pokeemerald.learnset_apply import apply_learnsets
from .appliers.pokeemerald.move_apply import apply_moves
from .appliers.pokeemerald.resolution import build_resolution_map
from .appliers.pokeemerald.species_apply import apply_species
from .appliers.pokeemerald.type_chart_apply import apply_type_chart
from .behavior import render_manifest, render_packet
from .harvest.harvester import apply_proposals, propose_changes
from .model import Ruleset
from .model.holds import HoldSet, load_holds
from .model.target_edits import TargetEdits, load_target_edits
from .report import ApplyReport
from .seed.extractor import seed_from_fork
from .seed.writer import write_ruleset

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_RULESET = _REPO_ROOT / "ruleset"
_DEFAULT_SNAPSHOT = _DEFAULT_RULESET / ".base" / "1.11.2.json"
_DEFAULT_DIST = _REPO_ROOT / "frontend" / "dist"
# The Target registry (gitignored, machine-specific). Mirrors
# web/app.py::DEFAULT_TARGETS_PATH so the CLI and the web layer read one file.
_DEFAULT_TARGETS = _REPO_ROOT / "targets.json"
# Apply resolves in dependency tiers: existing owned moves are retuned first, then
# missing owned content is created, then species scalars, learnsets, evolutions, and
# finally the type chart. Move-retune runs before create so each owned move is
# handled by exactly one tier (edited when present, created when absent).
_APPLY_CATEGORIES = ("moves", "create", "species", "learnset", "evolution", "type-chart")


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
        "--engine",
        choices=("pokeemerald", "essentials", "polishedcrystal", "rejuv"),
        default="pokeemerald",
        help="Target engine (default: pokeemerald). 'essentials' writes Pokémon "
        "Essentials PBS text; the dialect (16.2 vs modern v21) is auto-detected from "
        "the target's file shape — override with --dialect.",
    )
    apply.add_argument(
        "--category",
        choices=("all", "abilities", "moves", "create", "species", "learnset", "evolution", "type-chart", "behaviors"),
        default="all",
        help="Which tier to apply (default: all). Not every tier exists on every engine; "
        "a tier absent from the chosen engine is simply a no-op.",
    )
    apply.add_argument(
        "--ruleset", type=Path, default=_DEFAULT_RULESET, help="Ruleset folder to read."
    )
    apply.add_argument(
        "--dialect",
        choices=("auto", "essentials16", "essentials21"),
        default="auto",
        help=(
            "Essentials dialect to use (default: auto — detect from PBS file shape). "
            "'essentials16' forces 16.x flat-CSV PBS; 'essentials21' forces modern "
            "section-based PBS. Ignored when engine=pokeemerald."
        ),
    )
    apply.add_argument(
        "--force", action="store_true", help="Apply even if the target git tree is dirty."
    )
    apply.add_argument(
        "--as",
        dest="slug",
        default=None,
        help="Target slug, e.g. 'africanvs'. When given, loads per-Target holds "
        "(ruleset/targets/<slug>/holds.yaml) and additive edits (edits.yaml). Omit "
        "to apply the base Ruleset with no per-Target holds (today's behavior).",
    )
    apply.add_argument(
        "--no-create-species",
        dest="create_absent",
        action="store_false",
        default=True,
        help="Do NOT create species absent from the target; report them blocked "
        "instead. Use for a target with a small dex (e.g. Infinite Fusion 2 Hoenn) "
        "where creating the full national dex floods it with unusable stubs.",
    )
    apply.add_argument(
        "--no-sync",
        dest="sync",
        action="store_false",
        default=True,
        help="Do NOT mirror patch/ to the handheld afterwards. Only affects a "
        "target that has a 'sync' block in targets.json; others never sync.",
    )

    sync_cmd = sub.add_parser(
        "sync", help="Mirror an already-applied patch/ folder to the handheld."
    )
    sync_cmd.add_argument("--target", required=True, type=Path, help="Path to the fork.")

    save_backup = sub.add_parser(
        "save-backup", help="Pull the handheld's saves into the local backup folder."
    )
    save_backup.add_argument("--target", required=True, type=Path, help="Path to the fork.")

    harvest = sub.add_parser(
        "harvest", help="Propose Ruleset edits from a fork's in-game tuning."
    )
    harvest.add_argument("--fork", required=True, type=Path, help="Path to the fork.")
    harvest.add_argument(
        "--ruleset", type=Path, default=_DEFAULT_RULESET, help="Ruleset folder."
    )
    harvest.add_argument(
        "--dry-run", action="store_true", help="List proposals only; write nothing."
    )

    behaviors = sub.add_parser(
        "behaviors",
        help="List custom mechanics, or print one as an implementation packet.",
    )
    behaviors.add_argument(
        "--ruleset", type=Path, default=_DEFAULT_RULESET, help="Ruleset folder."
    )
    behaviors.add_argument(
        "--mechanic",
        help="Print the implementation packet for this ability or move (name or chrooked_id).",
    )
    behaviors.add_argument(
        "--engine",
        help="Engine whose hint to surface in the packet (e.g. pokeemerald, essentials).",
    )

    snapshot = sub.add_parser(
        "snapshot", help="Freeze a base checkout into the committed dex snapshot JSON."
    )
    snapshot.add_argument(
        "--base", required=True, type=Path, help="Path to the base 1.11.2 checkout."
    )
    snapshot.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_SNAPSHOT,
        help="Snapshot file to write (default: ruleset/.base/1.11.2.json).",
    )

    ui = sub.add_parser("ui", help="Serve the local web app (FastAPI + built React).")
    ui.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    ui.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000).")
    ui.add_argument(
        "--ruleset", type=Path, default=_DEFAULT_RULESET, help="Ruleset folder to serve."
    )
    ui.add_argument(
        "--snapshot",
        type=Path,
        default=_DEFAULT_SNAPSHOT,
        help="Base snapshot JSON to merge against.",
    )
    ui.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-restart the server when Python source changes (default: on). "
        "Use --no-reload to serve a single process.",
    )

    args = parser.parse_args(argv)
    if args.command == "snapshot":
        return _run_snapshot(args.base, args.out)
    if args.command == "ui":
        return _run_ui(args.host, args.port, args.ruleset, args.snapshot, args.reload)
    if args.command == "seed":
        return _run_seed(args.fork, args.base, args.ruleset)
    if args.command == "apply":
        return _run_apply(
            args.target, args.engine, args.category, args.ruleset, args.force,
            args.dialect, args.slug, args.create_absent, args.sync,
        )
    if args.command == "sync":
        return _run_sync_command(args.target)
    if args.command == "save-backup":
        return _run_save_backup_command(args.target)
    if args.command == "harvest":
        return _run_harvest(args.fork, args.ruleset, args.dry_run)
    if args.command == "behaviors":
        return _run_behaviors(args.ruleset, args.mechanic, args.engine)
    parser.error(f"unknown command {args.command}")
    return 2


def _run_behaviors(ruleset_dir: Path, mechanic: str | None, engine: str | None) -> int:
    ruleset = Ruleset.load(ruleset_dir)
    if mechanic is None:
        print(render_manifest(ruleset), end="")
        return 0
    spec = ruleset.behavior_for(mechanic)
    if spec is None:
        print(f"No behavior spec for {mechanic!r}.", file=sys.stderr)
        return 1
    print(render_packet(spec, engine), end="")
    return 0


def _run_harvest(fork: Path, ruleset_dir: Path, dry_run: bool) -> int:
    ruleset = Ruleset.load(ruleset_dir)
    resmap = build_resolution_map(fork, ruleset)
    proposals = propose_changes(fork, ruleset, resmap)

    if not proposals:
        print("Harvest: no drift found; the Ruleset already matches the fork.")
        return 0

    print(f"Harvest found {len(proposals)} proposed change(s):")
    for proposal in proposals:
        print(f"  {proposal.describe()}")

    if dry_run:
        print("(dry run — nothing written)")
        return 0

    accepted = [p for p in proposals if _confirm(p.describe())]
    if not accepted:
        print("Nothing accepted; the Ruleset is unchanged.")
        return 0

    touched = apply_proposals(ruleset_dir, ruleset, accepted)
    print(f"Updated {len(touched)} species file(s): {', '.join(sorted(touched))}")
    return 0


def _confirm(message: str) -> bool:
    answer = input(f"Accept {message}? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def _apply_rejuv(target: Path, category: str, ruleset, report: ApplyReport) -> None:
    """Emit the Rejuvenation patch/ overlay (delta Ruby definition files)."""
    from .appliers.rejuv import apply_rejuv

    written = apply_rejuv(target, ruleset, report, category=category)
    print(f"rejuv: {len(written)} file(s) written under patch/")


def _apply_pokeemerald(
    target: Path, category: str, ruleset, report: ApplyReport,
    holds: "HoldSet | None" = None,
) -> None:
    """`holds` pins chosen categories of chosen entities to the Target's own data
    (those rows report `held` and are not written). `evolution` and `type-chart`
    are not holdable — see model/holds.py for why."""
    holds = holds or HoldSet()
    resmap = build_resolution_map(target, ruleset)
    categories = _APPLY_CATEGORIES if category == "all" else (category,)
    if "moves" in categories:
        changed = apply_moves(target, ruleset, resmap, report, holds=holds)
        print(f"moves: {len(changed)} file(s) changed")
    if "create" in categories:
        changed = create_owned_content(target, ruleset, resmap, report, holds=holds)
        print(f"create: {len(changed)} file(s) changed")
    if "species" in categories:
        changed = apply_species(target, ruleset, resmap, report, holds=holds)
        print(f"species: {len(changed)} file(s) changed")
    if "learnset" in categories:
        changed = apply_learnsets(target, ruleset, resmap, report, holds=holds)
        print(f"learnset: {len(changed)} file(s) changed")
    if "evolution" in categories:
        changed = apply_evolutions(target, ruleset, resmap, report)
        print(f"evolution: {len(changed)} file(s) changed")
    if "type-chart" in categories:
        changed = apply_type_chart(target, ruleset, report)
        print(f"type-chart: {len(changed)} file(s) changed")


# Polished Crystal is apply-only Overrides: moves before the species-referencing
# categories, no create tier (a data-only Applier cannot author GB assembly —
# missing content becomes a blocked report entry, per the behaviors Boundary).
_POLISHEDCRYSTAL_CATEGORIES = ("moves", "learnset", "abilities")


def _apply_polishedcrystal(target: Path, category: str, ruleset, report: ApplyReport) -> None:
    from .appliers.polishedcrystal import ability_apply, learnset_apply, move_apply
    from .appliers.polishedcrystal.resolution import (
        build_resolution_map as pc_resolution_map,
    )

    import subprocess

    # Apply-only engine: no base pin. The record of *what* was patched is the
    # target's commit hash, printed alongside the report.
    result = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        print(f"target commit: {result.stdout.strip()}")

    # Learnset references resolve through stand-ins (meta.yaml) AND takeover
    # hints (a MoveDef's aka: polishedcrystal:) — a taken-over slot must catch
    # references to the move's display name. Explicit stand-ins win.
    takeover_refs = {
        m.name: str(dict(m.aka)["polishedcrystal"])
        for m in ruleset.moves.values()
        if dict(m.aka or {}).get("polishedcrystal")
    }
    standins = (ruleset.meta.get("standins") or {}).get("polishedcrystal") or {}
    resmap = pc_resolution_map(target, standins={**takeover_refs, **standins})
    categories = _POLISHEDCRYSTAL_CATEGORIES if category == "all" else (category,)
    if "moves" in categories:
        changed = move_apply.apply_moves(target, ruleset, resmap, report)
        print(f"moves: {len(changed)} file(s) changed")
    if "learnset" in categories:
        changed = learnset_apply.apply_learnsets(target, ruleset, resmap, report)
        print(f"learnset: {len(changed)} file(s) changed")
    if "abilities" in categories:
        changed = ability_apply.apply_abilities(target, ruleset, resmap, report)
        print(f"abilities: {len(changed)} file(s) changed")


# Essentials now covers the same tiers as pokeemerald. Evolution writes the
# pre-evolution's `Evolution` lines in pokemon.txt; type-chart edits the defender
# buckets in types.txt (a different shape than pokeemerald's matrix).
_ESSENTIALS_CATEGORIES = ("moves", "create", "species", "learnset", "evolution", "type-chart")


def _apply_essentials(target: Path, category: str, ruleset, report: ApplyReport) -> None:
    resmap = essentials_resolution.build_resolution_map(target, ruleset)
    categories = _ESSENTIALS_CATEGORIES if category == "all" else (category,)
    if "moves" in categories:
        changed = essentials_moves.apply_moves(target, ruleset, resmap, report)
        print(f"moves: {len(changed)} file(s) changed")
    if "create" in categories:
        changed = essentials_creation.create_owned_content(target, ruleset, resmap, report)
        print(f"create: {len(changed)} file(s) changed")
    if "species" in categories:
        changed = essentials_species.apply_species(target, ruleset, resmap, report)
        print(f"species: {len(changed)} file(s) changed")
    if "learnset" in categories:
        changed = essentials_learnset.apply_learnsets(target, ruleset, resmap, report)
        print(f"learnset: {len(changed)} file(s) changed")
    if "evolution" in categories:
        changed = essentials_evolution.apply_evolutions(target, ruleset, resmap, report)
        print(f"evolution: {len(changed)} file(s) changed")
    if "type-chart" in categories:
        changed = essentials_type_chart.apply_type_chart(target, ruleset, resmap, report)
        print(f"type-chart: {len(changed)} file(s) changed")


# The 16.2 dialect runs the same data tiers as v21 Essentials. Abilities are written
# FIRST so freshly-written ability rows register into the in-memory ResolutionMap before
# species_apply runs — ensuring a species that cites a brand-new Ruleset ability resolves
# its slot (not a partial). Move scalars follow, then species scalars, learnsets,
# evolutions, and finally the defender-bucket type chart. (Move effects → HEX functioncodes
# are #22.)
_ESSENTIALS162_CATEGORIES = ("abilities", "moves", "species", "learnset", "evolution", "type-chart", "behaviors")


def _apply_essentials162(
    target: Path, category: str, ruleset, report: ApplyReport,
    holds: "HoldSet | None" = None, target_edits: "TargetEdits | None" = None,
    create_absent: bool = True,
) -> None:
    """Apply the Ruleset's data tiers into a target's Essentials 16.2 PBS.

    Mirrors `_apply_essentials` but builds on the 16.2 I/O + format rules: per-stat
    BaseStats (Speed at index 3), `Type1`/`Type2` with mono-type Type2 drop, singular
    `HiddenAbility`, flat moves.txt CSV scalars, and the defender-bucket type chart.
    Honors `--category`; anything that cannot resolve is recorded in the Apply Report.

    `holds` pins chosen categories of chosen entities to the Target's own data (those
    are reported `held`, not written). `target_edits` layers additive per-Target edits
    on top (currently: extra learnset moves). Both default to empty.
    """
    holds = holds or HoldSet()
    target_edits = target_edits or TargetEdits()
    resmap = essentials162_resolution.build_resolution_map(target, ruleset)
    categories = _ESSENTIALS162_CATEGORIES if category == "all" else (category,)
    if "abilities" in categories:
        changed = essentials162_abilities.apply_abilities(
            target, ruleset, resmap, report, holds=holds
        )
        print(f"abilities: {len(changed)} file(s) changed")
    if "moves" in categories:
        changed = essentials162_moves.apply_moves(
            target, ruleset, resmap, report, holds=holds
        )
        print(f"moves: {len(changed)} file(s) changed")
    if "species" in categories:
        # Alt-forms live in pokemonforms.txt and are claimed FIRST, so species_apply
        # skips them instead of (wrongly) blocking them as missing from pokemon.txt.
        forms_changed, handled = essentials162_forms.apply_forms(
            target, ruleset, resmap, report
        )
        species_changed = essentials162_species.apply_species(
            target, ruleset, resmap, report, skip=handled, holds=holds,
            create_absent=create_absent,
        )
        changed = forms_changed | species_changed
        print(f"species: {len(changed)} file(s) changed")
    if "learnset" in categories:
        changed = essentials162_learnset.apply_learnsets(
            target, ruleset, resmap, report, holds=holds, target_edits=target_edits
        )
        print(f"learnset: {len(changed)} file(s) changed")
    if "evolution" in categories:
        changed = essentials162_evolution.apply_evolutions(target, ruleset, resmap, report)
        print(f"evolution: {len(changed)} file(s) changed")
    if "type-chart" in categories:
        changed = essentials162_type_chart.apply_type_chart(target, ruleset, resmap, report)
        print(f"type-chart: {len(changed)} file(s) changed")
    if "behaviors" in categories:
        # Install ported mechanics LAST — the ability data rows exist by now, and a
        # standalone plugin copy needs no earlier ordering. Flips DATA-ONLY honestly.
        changed = essentials162_behaviors.install_behaviors(target, ruleset, report)
        print(f"behaviors: {len(changed)} file(s) changed")


def _run_apply(
    target: Path,
    engine: str,
    category: str,
    ruleset_dir: Path,
    force: bool,
    dialect: str = "auto",
    slug: str | None = None,
    create_absent: bool = True,
    sync: bool = True,
) -> int:
    """Apply the Ruleset to a target fork.

    When engine is 'essentials' and dialect is 'auto', the PBS file shape is
    inspected to pick the right applier. A non-auto dialect forces the choice
    without reading any PBS files. An unrecognised format blocks with a clear
    message in the Apply Report and writes nothing to the target.

    When `slug` is given, per-Target holds and additive edits for that slug are
    loaded from `ruleset/targets/<slug>/` and honored by the applier. Omitting it
    applies the base Ruleset with no per-Target holds.
    """
    try:
        require_clean_git_status(target, force=force)
    except DirtyWorkingTree as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    # Essentials forks recompile PBS → Data/*.dat on boot; back Data/ up once
    # before writing so a bricking recompile is recoverable. Parity with the web
    # apply path. Abort if the net can't be made.
    if engine == "essentials":
        from .appliers.essentials.data_backup import (
            DataBackupError,
            backup_essentials_data,
        )

        try:
            backup = backup_essentials_data(target)
        except DataBackupError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            print(
                "Apply aborted to protect the game; free space or back up Data/ "
                "by hand, then retry.",
                file=sys.stderr,
            )
            return 1
        if backup["status"] == "created":
            print(f"Backed up Data/ → {backup['path']} (boot-recompile safety net).")
        elif backup["status"] == "kept":
            print(f"Data.bak already exists — left untouched ({backup['path']}).")

    ruleset = Ruleset.load(ruleset_dir)
    holds = load_holds(ruleset_dir, slug)
    target_edits = load_target_edits(ruleset_dir, slug)
    report = ApplyReport()

    from .appliers.dispatch import route_apply

    route_apply(
        target, engine, ruleset, report, category=category, dialect=dialect,
        holds=holds, target_edits=target_edits, create_absent=create_absent,
    )

    # When the format was unrecognized, route_apply writes a blocked entry and
    # returns without touching any files.  Surface the block to the console and
    # write the report so the user has a record, then exit non-zero.
    counts = report.counts()
    if counts["blocked"] > 0 and counts["applied"] == 0 and counts["partial"] == 0:
        # All entries are blocked — the format was unrecognized (essentials) or
        # some other total-block scenario.  Print the CLI-specific block message.
        if engine == "essentials":
            print(
                "blocked: unrecognized Essentials format. "
                "Use --dialect essentials16 or --dialect essentials21 to override."
            )
        json_path = report.write(target / "apply-report.md")
        print(
            f"Apply Report: applied={counts['applied']} "
            f"partial={counts['partial']} blocked={counts['blocked']} held={counts['held']}"
        )
        print(f"  {target / 'apply-report.md'}")
        print(f"  {json_path}")
        return 1

    json_path = report.write(target / "apply-report.md")
    print(
        f"Apply Report: applied={counts['applied']} "
        f"partial={counts['partial']} blocked={counts['blocked']} held={counts['held']}"
    )

    data_only = [e for e in report.entries if "DATA ONLY" in (e.reason or "")]
    if data_only:
        print(
            f"  ⚠ {len(data_only)} created entry/ies are DATA ONLY — their mechanics "
            "must be implemented in the target engine:"
        )
        for entry in data_only:
            print(f"      {entry.category} {entry.chrooked_id} ({entry.symbol})")
        print("  Run `chrooked-pokedex behaviors --mechanic <id> --engine <engine>` for a packet.")

    print(f"  {target / 'apply-report.md'}")
    print(f"  {json_path}")

    if sync:
        _sync_after_apply(target)
    return 0


def _sync_after_apply(target: Path) -> None:
    """Mirror patch/ to the handheld, if this Target has a sync block.

    A sync failure never fails the apply: the files written here are valid
    whether or not the device was reachable, so an asleep handheld gets an
    honest line, not a non-zero exit.
    """
    from .sync import run_save_backup, run_sync, sync_config_for_path

    config = sync_config_for_path(_DEFAULT_TARGETS, target)
    if config is None:
        return  # not a synced Target — the overwhelmingly common case
    result = run_sync(target, config)
    print(f"  {'✓' if result.ok else '⚠'} {_sync_line(result)}")
    if config.save_src and config.save_backup_dir:
        backup = run_save_backup(config)
        print(f"  {'✓' if backup.ok else '⚠'} {_sync_line(backup)}")


def _sync_line(result: "SyncResult") -> str:
    """One-line human summary of a transfer."""
    if not result.ok:
        return result.detail
    bits = [result.detail]
    if result.files is not None:
        bits.append(f"{result.files} file(s)")
    if result.seconds is not None:
        bits.append(f"{result.seconds}s")
    return " · ".join(bits)


def _run_sync_command(target: Path) -> int:
    """Mirror patch/ without applying. Unlike the apply tail, failure exits 1."""
    from .sync import run_sync, sync_config_for_path

    config = sync_config_for_path(_DEFAULT_TARGETS, target)
    if config is None:
        print(
            f"ERROR: no sync block for {target} in {_DEFAULT_TARGETS}. "
            "Add one to that Target's entry to enable syncing.",
            file=sys.stderr,
        )
        return 1
    result = run_sync(target, config)
    print(_sync_line(result), file=sys.stderr if not result.ok else sys.stdout)
    return 0 if result.ok else 1


def _run_save_backup_command(target: Path) -> int:
    """Pull the handheld's saves into the local backup folder."""
    from .sync import run_save_backup, sync_config_for_path

    config = sync_config_for_path(_DEFAULT_TARGETS, target)
    if config is None:
        print(f"ERROR: no sync block for {target} in {_DEFAULT_TARGETS}.", file=sys.stderr)
        return 1
    result = run_save_backup(config)
    print(_sync_line(result), file=sys.stderr if not result.ok else sys.stdout)
    return 0 if result.ok else 1


def _run_seed(fork: Path, base: Path, ruleset_dir: Path) -> int:
    _verify_base_version(base)
    data = seed_from_fork(fork, base)
    write_ruleset(data, ruleset_dir)

    counts = data.counts()
    _log_seed(ruleset_dir, fork, counts)
    print(f"Seeded Ruleset at {ruleset_dir}:")
    print(f"  species changed:       {counts['species_changed']}")
    print(f"  learnsets replaced:    {counts['learnsets_replaced']}")
    print(f"  evolutions changed:    {counts['evolutions_changed']}")
    print(f"  moves owned:           {counts['moves_owned']}")
    print(f"  abilities owned:       {counts['abilities_owned']}")
    print(f"  type-chart overrides:  {counts['type_chart_overrides']}")
    return 0


def _log_seed(ruleset_dir: Path, fork: Path, counts: dict) -> None:
    """Record one summary entry for a bulk seed (not per-entity spam)."""
    from . import ledger as ledgermod

    ledgermod.append(
        ruleset_dir,
        {
            "scope": "base",
            "kind": "seed",
            "chrooked_id": None,
            "source": "seed",
            "summary": dict(counts),
            "fork": str(fork),
        },
    )


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


def _run_snapshot(base: Path, out: Path) -> int:
    """Freeze base 1.11.2 into the committed dex snapshot. Deterministic: a re-run
    on an unchanged base rewrites byte-identical JSON, so `git status` stays clean."""
    from .web import snapshot as web_snapshot

    _verify_base_version(base)
    data = web_snapshot.build_snapshot(base)
    path = web_snapshot.write_snapshot(data, out)
    print(f"Wrote base snapshot: {path}")
    print(f"  species: {len(data['species'])}")
    return 0


def _run_ui(
    host: str,
    port: int,
    ruleset_dir: Path,
    snapshot_path: Path,
    reload: bool = False,
) -> int:
    """Serve the local web app. Imports of the web extra are deferred so the other
    subcommands work without `fastapi`/`uvicorn` installed."""
    try:
        import uvicorn

        from .web.app import create_app
    except ModuleNotFoundError as error:
        print(
            f"ERROR: the web extra is not installed ({error.name}). "
            'Run: pip install -e ".[web]"',
            file=sys.stderr,
        )
        return 1

    if not snapshot_path.exists():
        print(
            f"ERROR: base snapshot not found at {snapshot_path}. "
            "Generate it first: chrooked-pokedex snapshot --base <path-to-1.11.2>",
            file=sys.stderr,
        )
        return 1

    if not _DEFAULT_DIST.exists():
        print(
            "Note: frontend/dist not found — serving the API only. "
            "Run the Vite dev server (cd frontend && npm run dev) for the UI."
        )

    print(f"Serving chrooked-pokedex on http://{host}:{port}  (API under /api)")
    if reload:
        # Reload runs the app in a worker subprocess that re-imports the module
        # on each change, so config travels via env vars to the factory.
        os.environ["CHROOKED_RULESET"] = str(ruleset_dir)
        os.environ["CHROOKED_SNAPSHOT"] = str(snapshot_path)
        os.environ["CHROOKED_DIST"] = str(_DEFAULT_DIST)
        uvicorn.run(
            "chrooked_pokedex.web.app:create_app_from_env",
            factory=True,
            host=host,
            port=port,
            reload=True,
            reload_dirs=[str(_REPO_ROOT / "src")],
        )
        return 0

    app = create_app(
        ruleset_dir=ruleset_dir,
        snapshot_path=snapshot_path,
        dist_dir=_DEFAULT_DIST,
    )
    uvicorn.run(app, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
