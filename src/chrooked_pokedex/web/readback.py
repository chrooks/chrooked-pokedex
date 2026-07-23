"""Read-back diff — compare a Target's on-disk species against the Ruleset.

After an apply writes the Ruleset into a Target, In-Game Proof means reading the
applied entry back off disk and diffing it field-by-field against what the Ruleset
says it should be. A green Apply Report is NOT proof: form-join and clobber bugs
have shipped past it. This module is the pure differ — the route feeds it the
Ruleset expectation (the merged canon dex entry) and the Target's fresh on-disk
snapshot entry, per changed species, and renders one ``READ-BACK OK · N/N`` proof.
"""

from __future__ import annotations

from typing import Any

_STAT_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")
_ABILITY_SLOTS = ("primary", "secondary", "hidden")

# The overridable fields this differ knows how to compare. Evolution is excluded —
# the makeover slice does not rewrite evolution methods.
COMPARABLE_FIELDS = ("types", "stats", "abilities", "learnset")


def _norm_types(types: Any) -> list[str]:
    return [str(t).strip() for t in (types or [])]


def _learnset_key(rows: Any) -> list[tuple[int, str]]:
    """A learnset as a sorted, comparable set of ``(level, move)`` pairs."""
    out: list[tuple[int, str]] = []
    for row in rows or []:
        try:
            level = int(row.get("level", 0))
        except (TypeError, ValueError):
            level = 0
        out.append((level, str(row.get("move", "")).strip()))
    return sorted(out)


def _check(field: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"field": field, "expected": expected, "actual": actual, "ok": expected == actual}


def diff_species(
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
    *,
    fields: list[str],
) -> dict[str, Any]:
    """Diff one species' applied on-disk values against the Ruleset expectation.

    ``expected`` is the merged canon dex entry (the Ruleset's expectation);
    ``actual`` is the Target's fresh on-disk snapshot entry (``None`` if the
    species is missing on disk — every checked field then fails loudly). ``fields``
    is the subset of :data:`COMPARABLE_FIELDS` the makeover actually changed, so
    the read-back only asserts what was written.

    Returns ``{chrooked_id, name, checks: [...], ok_count, total, ok}`` where each
    check is ``{field, expected, actual, ok}``.
    """
    checks: list[dict[str, Any]] = []
    present = actual if isinstance(actual, dict) else {}
    checked = [f for f in fields if f in COMPARABLE_FIELDS]

    for field in checked:
        if field == "types":
            checks.append(
                _check("types", _norm_types(expected.get("types")), _norm_types(present.get("types")))
            )
        elif field == "stats":
            exp_stats = expected.get("stats") or {}
            act_stats = present.get("stats") or {}
            for key in _STAT_KEYS:
                exp_v = exp_stats.get(key)
                if exp_v is None:
                    continue
                checks.append(_check(f"stat:{key}", exp_v, act_stats.get(key)))
        elif field == "abilities":
            exp_ab = expected.get("abilities") or {}
            act_ab = present.get("abilities") or {}
            for slot in _ABILITY_SLOTS:
                exp_v = exp_ab.get(slot)
                if not exp_v:
                    continue
                checks.append(_check(f"ability:{slot}", exp_v, act_ab.get(slot)))
        elif field == "learnset":
            checks.append(
                _check("learnset", _learnset_key(expected.get("learnset")), _learnset_key(present.get("learnset")))
            )

    ok_count = sum(1 for c in checks if c["ok"])
    total = len(checks)
    return {
        "chrooked_id": expected.get("chrooked_id"),
        "name": expected.get("name") or expected.get("chrooked_id"),
        "missing": actual is None,
        "checks": checks,
        "ok_count": ok_count,
        "total": total,
        "ok": actual is not None and ok_count == total and total > 0,
    }


def read_back(
    species: list[dict[str, Any]],
) -> dict[str, Any]:
    """Roll per-species diffs into one proof artifact.

    ``species`` is a list of pre-diffed entries (each the output of
    :func:`diff_species`). Returns ``{species, ok_count, total, ok}`` — the
    headline ``N/N`` the workbench renders as ``READ-BACK OK · N/N``.
    """
    ok_count = sum(s["ok_count"] for s in species)
    total = sum(s["total"] for s in species)
    return {
        "species": species,
        "ok_count": ok_count,
        "total": total,
        "ok": all(s["ok"] for s in species) and bool(species),
    }
