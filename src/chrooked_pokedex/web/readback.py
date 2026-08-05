"""Read-back diff — compare a Target's on-disk species against the Ruleset.

After an apply writes the Ruleset into a Target, In-Game Proof means reading the
applied entry back off disk and diffing it field-by-field against what the Ruleset
says it should be. A green Apply Report is NOT proof: form-join and clobber bugs
have shipped past it. This module is the pure differ — the route feeds it the
Ruleset expectation (the merged canon dex entry) and the Target's fresh on-disk
snapshot entry, per changed species, and renders one ``READ-BACK OK · N/N`` proof.

Names are compared in RESOLUTION space, not raw strings: the Ruleset stores
display names ("Serene Grace") while Essentials PBS stores engine-internal symbols
("SERENEGRACE"). Comparing raw strings false-alarms on every ability/move/type. We
reuse the essentials applier's own ``internal_name`` derivation (and the
``aka.essentials`` hint priority) — the SAME Seam that wrote the symbols — so
"Serene Grace" ⇄ "SERENEGRACE" matches while "Levitate" vs "PIXILATE" still
mismatches. The report keeps the verbatim engine value (honest); only true diffs
render.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..appliers.essentials import vocab

_STAT_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")
_ABILITY_SLOTS = ("primary", "secondary", "hidden")

# The overridable fields this differ knows how to compare. Evolution is excluded —
# the makeover slice does not rewrite evolution methods, so it is never in the
# compared set (no normalization needed there; if it is added later, `_symbol`
# already covers species + item-param names).
COMPARABLE_FIELDS = ("types", "stats", "abilities", "learnset")


def _symbol(value: Any, aka_by_name: Mapping[str, Mapping[str, Any]] | None = None) -> str | None:
    """A name in Essentials resolution space, the way the applier resolved it.

    Reuses ``vocab.internal_name`` (``"Serene Grace" -> "SERENEGRACE"``); when the
    entity carries an explicit ``aka.essentials`` symbol hint, that symbol is the
    resolved value (the applier used it), still folded through ``internal_name`` so
    the comparison is case/separator-insensitive on BOTH sides. Idempotent on a
    value that is already an engine symbol (what the Target snapshot holds)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return ""
    aka = (aka_by_name or {}).get(text.casefold())
    if aka and aka.get("essentials"):
        return vocab.internal_name(str(aka["essentials"]))
    return vocab.internal_name(text)


def _check(field: str, expected: Any, actual: Any, ok: bool) -> dict[str, Any]:
    """A check row: the VERBATIM engine values (honest) + the resolution-space ok."""
    return {"field": field, "expected": expected, "actual": actual, "ok": ok}


def diff_species(
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
    *,
    fields: list[str],
    aka_by_name: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Diff one species' applied on-disk values against the Ruleset expectation.

    ``expected`` is the merged canon dex entry (the Ruleset's expectation);
    ``actual`` is the Target's fresh on-disk snapshot entry (``None`` if the
    species is missing on disk — every checked field then fails loudly). ``fields``
    is the subset of :data:`COMPARABLE_FIELDS` the makeover actually changed.
    ``aka_by_name`` maps a display name (case-folded) to its ``aka`` hints so an
    explicit engine symbol wins over the derived one.

    String families (types, abilities, learnset moves) compare in resolution space;
    stats compare numerically. Each check carries the VERBATIM expected/actual so a
    real mismatch shows what the engine actually holds.
    """
    checks: list[dict[str, Any]] = []
    present = actual if isinstance(actual, dict) else {}
    checked = [f for f in fields if f in COMPARABLE_FIELDS]

    def sym(value: Any) -> str | None:
        return _symbol(value, aka_by_name)

    for field in checked:
        if field == "types":
            exp = [str(t).strip() for t in (expected.get("types") or [])]
            act = [str(t).strip() for t in (present.get("types") or [])]
            ok = [sym(t) for t in exp] == [sym(t) for t in act]
            checks.append(_check("types", exp, act, ok))
        elif field == "stats":
            exp_stats = expected.get("stats") or {}
            act_stats = present.get("stats") or {}
            for key in _STAT_KEYS:
                exp_v = exp_stats.get(key)
                if exp_v is None:
                    continue
                act_v = act_stats.get(key)
                checks.append(_check(f"stat:{key}", exp_v, act_v, exp_v == act_v))
        elif field == "abilities":
            exp_ab = expected.get("abilities") or {}
            act_ab = present.get("abilities") or {}
            for slot in _ABILITY_SLOTS:
                exp_v = exp_ab.get(slot)
                if not exp_v:
                    continue
                act_v = act_ab.get(slot)
                is_ok = sym(exp_v) == sym(act_v)
                checks.append(_check(f"ability:{slot}", exp_v, act_v, is_ok))
        elif field == "learnset":
            exp_rows = _learnset_pairs(expected.get("learnset"), sym)
            act_rows = _learnset_pairs(present.get("learnset"), sym)
            checks.append(
                _check(
                    "learnset",
                    _learnset_display(expected.get("learnset")),
                    _learnset_display(present.get("learnset")),
                    exp_rows == act_rows,
                )
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


def _learnset_level(row: Any) -> int:
    try:
        return int(row.get("level", 0))
    except (TypeError, ValueError):
        return 0


def _learnset_pairs(rows: Any, sym) -> list[tuple[int, str | None]]:
    """A learnset as a sorted set of ``(level, move-symbol)`` for comparison.

    The Target snapshot carries the verbatim engine symbol on ``move_id`` — prefer
    it over the rendered display name, which does not always round-trip: Rejuv
    renders ``:STOMPINGTANTRUM`` as "Stomp Tantrum", which re-derives to
    ``STOMPTANTRUM`` and false-alarms on a learnset the applier wrote correctly.
    Ruleset rows have no ``move_id`` and fall back to the display name."""
    return sorted(
        (_learnset_level(r), sym(r.get("move_id") or r.get("move", ""))) for r in (rows or [])
    )


def _learnset_display(rows: Any) -> list[tuple[int, str]]:
    """The verbatim ``(level, move)`` rows for the report (honest display)."""
    return sorted((_learnset_level(r), str(r.get("move", "")).strip()) for r in (rows or []))


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
