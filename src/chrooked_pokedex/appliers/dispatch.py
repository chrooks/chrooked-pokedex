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

    Side effects: modifies ``report`` in-place by appending ``ReportEntry``
    objects.  All file I/O is in the applier functions, not here.
    """
    # --- pokeemerald path ---------------------------------------------------
    if engine != "essentials":
        # Imported inline to avoid circular: cli → dispatch → cli.
        from ..cli import _apply_pokeemerald

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

        _apply_essentials162(target, category, ruleset, report)
    else:
        # Imported inline to avoid circular: cli → dispatch → cli.
        from ..cli import _apply_essentials

        _apply_essentials(target, category, ruleset, report)
