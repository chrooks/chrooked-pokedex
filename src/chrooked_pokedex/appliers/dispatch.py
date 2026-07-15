"""Shared engine+dialect dispatcher for the apply pipeline.

This module holds the detect-then-route logic that ``cli._run_apply`` and
``web/targets._run_applier`` both need, factored out so the two entry points
cannot drift apart (D-DRY).

``route_apply`` does NOT print or write ``apply-report.md``; those side effects
belong to each entry point (CLI keeps its prints; the web layer returns JSON).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

# These two have no back-reference to cli.py — safe at module level and
# patchable by tests (patch("chrooked_pokedex.appliers.dispatch.detect_dialect")).
from .essentials.dialect import detect_dialect
from ..model.holds import HoldSet
from ..model.target_edits import TargetEdits
from ..report import ReportEntry

if TYPE_CHECKING:
    from ..model import Ruleset
    from ..report import ApplyReport


def route_apply(
    target: Path,
    engine: str,
    ruleset: "Ruleset",
    report: "ApplyReport",
    *,
    category: str = "all",
    dialect: str = "auto",
    holds: "HoldSet | None" = None,
    target_edits: "TargetEdits | None" = None,
    create_absent: bool = True,
) -> None:
    """Detect the format, dispatch to the right applier, and mutate ``report``.

    For engine='essentials', auto-detects the PBS dialect (essentials16 →
    essentials162 applier; everything else → essentials v21 applier) unless
    ``dialect`` is set to an explicit key.  When dialect detection returns None
    (unrecognized format) the function appends a single ``blocked`` entry to
    ``report`` and writes nothing to the target — an Honest Signifier that the
    tool cannot proceed (D-unknown).

    For engine='pokeemerald' the pokeemerald applier is used directly;
    ``dialect`` is ignored.

    ``holds`` (per-Target category stand-downs) and ``target_edits`` (additive
    per-Target edits) are honored by the essentials162 applier; for other engines
    they are accepted but not yet wired. Both default to empty, so an apply with no
    slug behaves exactly as before.

    Side effects: modifies ``report`` in-place by appending ``ReportEntry``
    objects.  All file I/O is in the applier functions, not here.
    """
    holds = holds or HoldSet()
    target_edits = target_edits or TargetEdits()

    # --- polishedcrystal path -------------------------------------------------
    if engine == "polishedcrystal":
        # Imported inline to avoid circular: cli → dispatch → cli.
        from ..cli import _apply_polishedcrystal

        _warn_unsupported_target_layers(holds, target_edits, "polishedcrystal", report)
        _apply_polishedcrystal(target, category, ruleset, report)
        return

    # --- pokeemerald path ---------------------------------------------------
    if engine != "essentials":
        # Imported inline to avoid circular: cli → dispatch → cli.
        from ..cli import _apply_pokeemerald

        _warn_unsupported_target_layers(holds, target_edits, "pokeemerald", report)
        _apply_pokeemerald(target, category, ruleset, report)
        return

    # --- essentials path ----------------------------------------------------
    resolved_dialect = dialect
    if dialect == "auto":
        resolved_dialect = detect_dialect(target)  # type: ignore[assignment]
        if resolved_dialect is None:
            report.add(
                ReportEntry(
                    status="blocked",
                    category="(all)",
                    chrooked_id="(all)",
                    reason=(
                        "blocked: unrecognized Essentials format — "
                        "PBS/moves.txt and PBS/pokemon.txt do not match a known "
                        "dialect (essentials16 or essentials21). "
                        "Use --dialect to force one explicitly."
                    ),
                )
            )
            return

    if resolved_dialect == "essentials16":
        # Imported inline to avoid circular: cli → dispatch → cli.
        from ..cli import _apply_essentials162

        _apply_essentials162(
            target, category, ruleset, report, holds=holds, target_edits=target_edits,
            create_absent=create_absent,
        )
    else:
        # Imported inline to avoid circular: cli → dispatch → cli.
        from ..cli import _apply_essentials

        _warn_unsupported_target_layers(holds, target_edits, "essentials21", report)
        _apply_essentials(target, category, ruleset, report)


def _warn_unsupported_target_layers(
    holds: HoldSet, target_edits: TargetEdits, engine: str, report: "ApplyReport"
) -> None:
    """Record a blocked entry when holds/edits are set for an engine that ignores them.

    Per-Target holds and additive edits are honored only by the essentials16 (16.2)
    applier so far. Without this note, a hold registered against a pokeemerald or
    essentials21 Target would be silently ignored — and silently clobber the Target's
    own data. Surfacing it keeps the apply honest (no silent stand-down failure).
    """
    if not holds.held and not target_edits.learnset_add:
        return
    report.add(
        ReportEntry(
            status="blocked",
            category="(holds)",
            chrooked_id="(all)",
            reason=(
                f"per-Target holds/edits are not yet honored on the {engine} engine "
                "(supported on essentials16 only); the Target's data was written from "
                "the base Ruleset without standing down. Apply with an essentials16 "
                "Target, or remove the holds for this Target."
            ),
        )
    )
