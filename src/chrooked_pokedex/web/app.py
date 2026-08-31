"""The FastAPI application factory.

`create_app` wires the API routers over a Ruleset folder and a base snapshot
file. It loads both *per request* so an edit to `ruleset/` shows up on the next
call without a server restart — the same fail-fast loader gates every read.

In production the built React assets under `frontend/dist` are mounted at the
root; in dev that directory is absent and only the API is served (the Vite dev
server hosts the SPA separately).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import distribute as distmod
from .. import ledger as ledgermod
from ..behavior import render_packet
from ..env import load_env_file
from ..fingerprint import hash_ruleset_dir
from ..model import Ruleset, evolution_methods
from ..model.holds import hold_filtered_ruleset, load_holds
from . import collections as colmod
from . import crud as crudmod
from . import design_log as designlogmod
from . import dex as dexmod
from . import folder_picker as pickermod
from . import llm as llmmod
from . import lore as loremod
from . import readback as readbackmod
from . import snapshot as snapmod
from . import suggest as suggestmod
from . import save_sync
from . import targets as targetsmod

# The learnset pacing-band rubric — a single JSON source of truth served to the
# workbench (and derivable by the suggest-skill prose). Loaded once at import.
_LEARNSET_RUBRIC_PATH = Path(__file__).resolve().parent / "learnset_rubric.json"

_logger = logging.getLogger(__name__)

# The Target registry lives at the project root by default (D4): a gitignored
# `targets.json` holding machine-specific fork paths, never canon.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_TARGETS_PATH = _PROJECT_ROOT / "targets.json"


def _cap_to_families(
    ids: list[str], evo: "distmod.EvolutionIndex", limit: int
) -> list[str]:
    """Trim a recipient id list to the first ``limit`` distinct evolution families.

    Order is preserved (best-first from the caller). Every member of an accepted
    family stays; the first member of a family beyond the budget is dropped, so
    the size budget counts FAMILIES, not individual mons.
    """
    lines: list[str] = []
    kept: list[str] = []
    for cid in ids:
        line_id = evo.line_of.get(cid, cid)
        if line_id not in lines:
            if len(lines) >= limit:
                continue
            lines.append(line_id)
        kept.append(cid)
    return kept


def _cap_ability_rows_to_families(
    rows: list[dict[str, Any]], evo: "distmod.EvolutionIndex", limit: int
) -> list[dict[str, Any]]:
    """Trim {species, slot} distribution rows to the first ``limit`` families.

    The ability-distribution rubric ASKS for at most ``limit`` families, but the
    model over-produces on a broad prompt; this enforces the pre-request size
    budget deterministically (the rows-shaped twin of :func:`_cap_to_families`).
    Best-first order is preserved.
    """
    lines: list[str] = []
    kept: list[dict[str, Any]] = []
    for row in rows:
        species = row.get("species", "")
        line_id = evo.line_of.get(species, species)
        if line_id not in lines:
            if len(lines) >= limit:
                continue
            lines.append(line_id)
        kept.append(row)
    return kept


def create_app(
    *,
    ruleset_dir: Path,
    snapshot_path: Path = snapmod.DEFAULT_SNAPSHOT_PATH,
    dist_dir: Path | None = None,
    targets_path: Path | None = None,
    llm_provider: llmmod.LlmProvider | None = None,
    lore_provider: loremod.LoreProvider | None = None,
) -> FastAPI:
    # Load a repo-root `.env` so provider keys/config are available to the LLM
    # adapter (read lazily at request time). Covers the non-reload `ui` path that
    # builds the app directly; idempotent with create_app_from_env. Real env wins.
    load_env_file()

    app = FastAPI(title="chrooked-pokedex", version="0.1.0")
    ruleset_dir = Path(ruleset_dir)
    snapshot_path = Path(snapshot_path)

    # The LLM Port hangs off app.state so tests inject a mock (no real API call,
    # no key) and the real Adapter is built lazily only when a suggest fires.
    # `None` means "build the configured LiteLLM Adapter on first use".
    app.state.llm_provider = llm_provider

    # The lore Port hangs off app.state the same way, and is replaced the same way
    # in tests. `None` means "build the real HTTP Adapter on first use" — it needs
    # the snapshot's species ids to map a form back to its base, and the snapshot
    # is loaded per request, not here.
    app.state.lore_provider = lore_provider

    # Per-app Target state on app.state for clean test isolation: the registry
    # path, a per-fork lock registry, and the per-Target snapshot cache (D2/D4).
    app.state.targets_registry = targetsmod.TargetRegistry(
        Path(targets_path) if targets_path is not None else DEFAULT_TARGETS_PATH
    )
    app.state.targets_state = targetsmod.TargetState()

    # Dex read-cache (#59): the base⊕Ruleset merge is deterministic and read-heavy,
    # so cache it keyed on (snapshot identity, ruleset fingerprint). A changed input
    # is a new key — no manual invalidation, never a stale dex. Single slot: a new
    # key overwrites the old. `# ponytail:` one global lock, fine for one process.
    _dex_cache: dict[str, Any] = {"key": None, "dex": None}
    _dex_cache_lock = threading.Lock()
    app.state.dex_cache_stats = {"hits": 0, "misses": 0}

    def _dex_cache_key() -> tuple[Any, ...] | None:
        # Stat (not read) the 2.9 MB snapshot for cheap identity; fingerprint the
        # Ruleset bytes WITHOUT a full load so a hit can skip the load entirely.
        try:
            st = snapshot_path.stat()
        except OSError:
            return None
        return ((st.st_mtime_ns, st.st_size), hash_ruleset_dir(ruleset_dir))

    def _load_snapshot_or_503() -> dict[str, Any]:
        """Load the base snapshot, or 503 with an actionable message.

        The realistic failure is that the snapshot was never generated, is
        corrupt, or is valid JSON of the wrong shape. Only the dex routes merge
        onto the base, so only they call this; the Ruleset-owned collection
        routes never touch the snapshot.
        """
        try:
            snapshot = snapmod.load_snapshot(snapshot_path)
            if "species" not in snapshot:
                raise ValueError("missing top-level 'species' key")
            return snapshot
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Base snapshot unreadable at {snapshot_path}: {error}. "
                    "Generate it with `chrooked-pokedex snapshot --base <path>`."
                ),
            ) from error

    def _load_ruleset_or_503() -> Ruleset:
        """Load the Ruleset, or 503 — never a raw 500 with a traceback.

        Every route reloads the Ruleset per request (so edits to `ruleset/` show
        on reload). A malformed YAML or a failed validation there must surface as
        an actionable 503, not an unhandled parser/validation error. The broad
        catch is deliberate: the loader can raise yaml/Key/Value errors and all
        of them mean "the Ruleset on disk is unreadable", which is a 503.
        """
        try:
            return Ruleset.load(ruleset_dir)
        except Exception as error:  # noqa: BLE001 — see docstring
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Ruleset at {ruleset_dir} could not be loaded: "
                    f"{type(error).__name__}: {error}."
                ),
            ) from error

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dex")
    def get_dex() -> list[dict[str, Any]]:
        key = _dex_cache_key()
        if key is not None:
            with _dex_cache_lock:
                if _dex_cache["key"] == key:
                    app.state.dex_cache_stats["hits"] += 1
                    # Returns the cached list by reference (no copy — copying it
                    # would re-walk ~1000 species per hit and erase the win).
                    # Contract: the cached dex is READ-ONLY; callers must not
                    # mutate it. FastAPI only serializes (reads) it.
                    return _dex_cache["dex"]
        snapshot = _load_snapshot_or_503()
        dex = dexmod.build_dex(snapshot, _load_ruleset_or_503())
        if key is not None:
            with _dex_cache_lock:
                _dex_cache["key"] = key
                _dex_cache["dex"] = dex
                app.state.dex_cache_stats["misses"] += 1
        return dex

    @app.get("/api/dex/{chrooked_id}")
    def get_dex_entry(chrooked_id: str) -> dict[str, Any]:
        snapshot = _load_snapshot_or_503()
        entry = dexmod.build_dex_entry(snapshot, _load_ruleset_or_503(), chrooked_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"No species with chrooked_id {chrooked_id!r}."
            )
        return entry

    @app.get("/api/moves")
    def get_moves() -> list[dict[str, Any]]:
        # Canon moves reach species parity: the full base snapshot ⊕ Ruleset,
        # merged like the dex (was the sparse Ruleset-only list before this slice).
        snapshot = _load_snapshot_or_503()
        return dexmod.build_moves(snapshot, _load_ruleset_or_503())

    @app.get("/api/abilities")
    def get_abilities() -> list[dict[str, Any]]:
        # Canon abilities reach species parity: the full base snapshot ⊕ Ruleset,
        # merged like the dex (was the sparse Ruleset-only list before this slice).
        snapshot = _load_snapshot_or_503()
        return dexmod.build_abilities(snapshot, _load_ruleset_or_503())

    @app.get("/api/statuses")
    def get_statuses() -> list[dict[str, Any]]:
        # No snapshot argument: statuses are Ruleset-owned outright, not Overrides,
        # because the base snapshot carries no status data to diff against.
        return dexmod.build_statuses(_load_ruleset_or_503())

    @app.get("/api/type-chart")
    def get_type_chart() -> list[dict[str, Any]]:
        # Canon type chart reaches parity: the full base matrix ⊕ Ruleset, merged
        # per-cell like the dex (was the sparse Ruleset-only list before this slice).
        snapshot = _load_snapshot_or_503()
        return dexmod.build_type_chart(snapshot, _load_ruleset_or_503())

    @app.get("/api/behaviors")
    def get_behaviors() -> list[dict[str, Any]]:
        return colmod.build_behaviors(_load_ruleset_or_503())

    @app.get("/api/meta/evolution-methods")
    def get_evolution_methods() -> list[dict[str, Any]]:
        # The canonical evolution-method catalog for the editor's Method dropdown.
        # Served from the model table so the UI and the Appliers can't drift.
        return evolution_methods.public_list()

    @app.get("/api/meta/learnset-rubric")
    def get_learnset_rubric() -> dict[str, Any]:
        # The level-up BP pacing bands as data — the single source of truth the
        # Makeover Workbench annotates learnset rows against (a 75BP move at L8
        # shows a BAND ≤60 flag). Served verbatim from the repo JSON so the SPA
        # never hardcodes the bands and the skill prose can derive from the same
        # file. Read per request so an edit to the file shows without a restart.
        return _load_learnset_rubric()

    def _load_learnset_rubric() -> dict[str, Any]:
        try:
            return json.loads(_LEARNSET_RUBRIC_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=503,
                detail=f"Learnset rubric unreadable at {_LEARNSET_RUBRIC_PATH}: {error}.",
            ) from error

    @app.get("/api/ledger")
    def get_ledger(
        scope: str | None = None,
        kind: str | None = None,
        chrooked_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """The Change Ledger, newest-first, filterable by scope/kind/chrooked_id."""
        entries = ledgermod.read(
            ruleset_dir, scope=scope, kind=kind, chrooked_id=chrooked_id, limit=limit
        )
        return {"entries": entries}

    @app.post("/api/design-log")
    def append_design_log(payload: dict[str, Any] | None = None) -> dict[str, str]:
        """Append one dated makeover section to ``ruleset/DESIGN-LOG.md``.

        The auto tail of a workbench makeover harvests the direction picked and the
        corrections given in the tweak loops, confirms them on one editable line,
        and posts here. This route validates (a line name + a direction are
        required) and appends — never rewrites history. Returns the appended
        section verbatim so the UI can confirm exactly what landed.

        Missing line/direction → 422 with the honest message; nothing is written.
        """
        body = payload or {}
        try:
            section = designlogmod.append_entry(
                ruleset_dir / "DESIGN-LOG.md",
                line=body.get("line", ""),
                direction=body.get("direction", ""),
                new_mechanics=body.get("new_mechanics"),
                corrections=body.get("corrections"),
            )
        except designlogmod.DesignLogError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"section": section}

    # --- Write routes (Milestone 2a): species / moves / abilities ----------- #
    # Each write validates by reloading through the loader; a rejected edit is a
    # 422 carrying the loader's own message and nothing is written. The UI never
    # commits — Chris reviews `git diff` himself.

    def _422(error: crudmod.ValidationError) -> HTTPException:
        return HTTPException(status_code=422, detail=str(error))

    def _scope_dir(scope: str):
        """Resolve an edit scope to its write directory (base or a Target namespace).

        For a ``target:<slug>`` scope, look up the bound Target so the namespace's
        ``meta.yaml`` records the engine/label. A malformed scope raises
        ``ValidationError`` (caller maps to 422).
        """
        engine = label = None
        if scope and scope.startswith("target:"):
            slug = scope.split(":", 1)[1].strip()
            for target in app.state.targets_registry.list():
                if target.namespace == slug:
                    engine, label = target.engine, target.label
                    break
        return crudmod.resolve_scope_dir(ruleset_dir, scope, engine=engine, label=label)

    def _effective(target):
        """The effective Ruleset for a Target (base ⊕ its Override namespace).

        Returns ``(effective_ruleset, overlay)`` — the composed Ruleset the dex
        read and apply both consume, plus the raw overlay (or None) for badge data.
        """
        base = _load_ruleset_or_503()
        overlay = targetsmod.load_target_overlay(ruleset_dir, target)
        return targetsmod.effective_ruleset(base, overlay), overlay

    def _display_effective(target):
        """The effective Ruleset for a Target's read-only BACKDROP views.

        Same as ``_effective`` but with per-Target holds applied: a held category is
        cleared off the Override so the backdrop shows the Target's own data, matching
        what an apply would keep. Display only — the apply path uses ``_effective``
        plus the separate HoldSet so it can still report ``held`` rows.
        """
        effective, overlay = _effective(target)
        holds = load_holds(ruleset_dir, target.namespace)
        return hold_filtered_ruleset(effective, holds), overlay

    @app.get("/api/species/{chrooked_id}")
    def get_species_override(chrooked_id: str) -> dict[str, Any]:
        # The raw Override (overrides-only), distinct from the merged /api/dex
        # entry — the species editor needs exactly the changed fields so a save
        # round-trips them without writing base values back as Overrides.
        ruleset = _load_ruleset_or_503()
        # Bridge a backdrop-launched form id to canon exactly as the PUT below
        # does. Read and write MUST agree on identity: every editor and accept
        # path is a GET-modify-PUT, so an id the write resolves but the read
        # 404s on makes the client fabricate a blank Override and clobber every
        # field it did not set. Under a Rejuv backdrop that is how
        # `goodra--hisuianform` wiped goodrahisui's abilities and then its stats.
        chrooked_id = dexmod.resolve_form_id(_load_snapshot_or_503(), chrooked_id)
        override = ruleset.species.get(chrooked_id)
        if override is None:
            raise HTTPException(
                status_code=404,
                detail=f"No species Override for {chrooked_id!r}.",
            )
        return crudmod.serialize_species(override)

    @app.put("/api/species/{chrooked_id}")
    def put_species(
        chrooked_id: str, payload: dict[str, Any], scope: str = "base"
    ) -> dict[str, Any]:
        try:
            # Referential write-gate (ac9): reject a BASE write whose types / ability
            # names / learnset moves don't resolve against the merged view (base ⊕
            # owned content), naming the offending field. Only base scope — a
            # target-scoped re-theme resolves against that fork's own universe (the
            # target engine validates it on apply), not the base pools. Sits beside
            # the loader gate; seed/harvest/Ruleset.load never run it.
            if scope == "base":
                snapshot = _load_snapshot_or_503()
                ruleset = _load_ruleset_or_503()
                # Bridge a backdrop-launched form id to canon so the write lands on
                # the canon file (`marowakalola`), not the Rejuv slug. Resolve the
                # payload's OWN id through the same bridge rather than overwriting it:
                # a backdrop id on either side maps to canon and agrees, but a genuine
                # path/payload mismatch still resolves to two different ids and 422s.
                chrooked_id = dexmod.resolve_form_id(snapshot, chrooked_id)
                if isinstance(payload.get("chrooked_id"), str):
                    payload = {
                        **payload,
                        "chrooked_id": dexmod.resolve_form_id(
                            snapshot, payload["chrooked_id"]
                        ),
                    }
                crudmod.validate_species_references(
                    {**payload, "chrooked_id": chrooked_id},
                    type_names={t.casefold() for t in dexmod.build_type_pool(snapshot, ruleset)},
                    move_names={
                        row["move"].casefold()
                        for row in dexmod.build_move_pool(snapshot, ruleset)
                    },
                    ability_names={
                        entry["name"].casefold()
                        for entry in dexmod.build_abilities(snapshot, ruleset)
                        if entry.get("name")
                    },
                )
            return crudmod.upsert_species(
                _scope_dir(scope), chrooked_id, payload, ledger_dir=ruleset_dir, scope=scope
            )
        except crudmod.ValidationError as error:
            raise _422(error) from error

    def _suggest_entry(
        snapshot: dict[str, Any],
        ruleset: Ruleset,
        chrooked_id: str,
        payload: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        """The species entry a suggest call reasons about: canon first, then backdrop.

        A backdrop-launched makeover hands us a Target-form id (`marowak--
        alolanform`); the makeover operates on canon (`marowakalola`), so bridge
        it. A Target-ORIGINAL form (Rejuv's `breloom--aevianform`) has no canon
        entry at all — for those the payload's `target` names the backdrop it was
        launched from, and the entry comes from that Target's dex (target ⊕
        effective Ruleset): exactly what the workbench shows. The proposal POOLS
        stay canon either way — an accepted draft is written to the Ruleset and
        must resolve there. An id neither side knows is still an honest 404.
        """
        resolved = dexmod.resolve_form_id(snapshot, chrooked_id)
        entry = dexmod.build_dex_entry(snapshot, ruleset, resolved)
        if entry is not None:
            return resolved, entry
        target_id = (payload or {}).get("target")
        if isinstance(target_id, str) and target_id.strip():
            try:
                target = app.state.targets_registry.get(target_id.strip())
                effective, overlay = _display_effective(target)
                # ponytail: builds the whole backdrop dex to pick one entry —
                # cached snapshot underneath, and trivial next to the LLM call
                # this context feeds.
                backdrop = targetsmod.target_dex(
                    target,
                    effective,
                    app.state.targets_state,
                    base_snapshot=snapshot,
                    overlay=overlay,
                )
            except targetsmod.TargetError as error:
                raise _target_error(error) from error
            for candidate in backdrop:
                if candidate.get("chrooked_id") == chrooked_id:
                    return chrooked_id, candidate
        raise HTTPException(
            status_code=404, detail=f"No species with chrooked_id {chrooked_id!r}."
        )

    @app.post("/api/species/{chrooked_id}/suggest/ability")
    def suggest_species_ability(
        chrooked_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Propose a best-fit EXISTING ability for a species — never writes.

        Assembles context server-side (the merged dex entry + the full ability
        pool), runs ONE bounded Port call, and returns the reusable
        ``{draft, rationale, alternatives}`` contract. The accept path is the
        existing ``PUT /api/species/{id}`` (the loader Boundary), not this route.

        Honest errors: a missing key / upstream failure (`LlmError`) → 503; an
        unknown species or a hallucinated ability (`SuggestError`) → 422 — never
        a raw 500 traceback, and the provider key never reaches the client.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        chrooked_id, entry = _suggest_entry(snapshot, ruleset, chrooked_id, payload)
        abilities = dexmod.build_abilities(snapshot, ruleset)
        direction = (payload or {}).get("direction")
        # Slots the author has locked in the workbench: proposals must leave them
        # unchanged. Non-list / non-string payloads are ignored, not a 422.
        raw_locked = (payload or {}).get("locked")
        locked = [s for s in raw_locked if isinstance(s, str)] if isinstance(raw_locked, list) else None
        # Researched lore, opted into per call. Anything unrecognized normalizes
        # to off, so a typo in the body never starts a network fetch.
        lore_mode = suggestmod.normalize_lore_mode((payload or {}).get("lore"))
        try:
            response = suggestmod.suggest_ability(
                provider=_llm_provider(),
                entry=entry,
                abilities=abilities,
                direction=direction,
                locked=locked,
                lore_mode=lore_mode,
                lore_provider=_lore_provider(snapshot, lore_mode),
            )
            _record_lore(chrooked_id, "ability", response)
            return response
        except suggestmod.SuggestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            # A recoverable transport/config failure: surface the honest message
            # (which never carries the key) as a 503, not an unhandled 500.
            raise HTTPException(status_code=503, detail=str(error)) from error

    def _llm_provider() -> llmmod.LlmProvider:
        """The injected mock, or the configured LiteLLM Adapter built on demand.

        Lazy so importing the app never needs `litellm` or a key; the Adapter is
        constructed only when a real suggest runs with no mock injected.
        """
        if app.state.llm_provider is None:
            app.state.llm_provider = llmmod.build_provider()
        return app.state.llm_provider

    def _lore_provider(
        snapshot: dict[str, Any], lore_mode: str
    ) -> loremod.LoreProvider | None:
        """The lore Port, built on demand — and only when a caller asked for lore.

        Returns ``None`` for the off mode so the default path never even
        constructs a fetcher, let alone calls one. The real Adapter is seeded with
        the snapshot's species ids: that is how a form id (`marowakalola`) falls
        back to the base species PokeAPI actually holds (`marowak`).
        """
        if lore_mode == "off":
            return None
        if app.state.lore_provider is None:
            app.state.lore_provider = loremod.HttpLoreProvider(
                known_species=(snapshot.get("species") or {}).keys()
            )
        return app.state.lore_provider

    def _record_lore(
        chrooked_id: str, capability: str, response: dict[str, Any]
    ) -> None:
        """Ledger one line per lore-on suggestion, carrying its provenance verbatim.

        The point is attribution over days: the author is comparing full against
        condensed injection, and a week later the only honest record of which ran
        for which species is this line. An off suggestion writes nothing — the
        ledger is a history of what happened, not of what was declined.
        """
        provenance = response.get("lore")
        if not isinstance(provenance, dict) or provenance.get("mode") == "off":
            return
        ledgermod.append(
            ruleset_dir,
            {
                "kind": "suggest",
                "scope": "base",
                "source": "web-suggest",
                "chrooked_id": chrooked_id,
                "capability": capability,
                "lore": dict(provenance),
            },
        )

    @app.post("/api/species/{chrooked_id}/suggest/typing")
    def suggest_species_typing(
        chrooked_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Propose a best-fit typing (1-2 types) for a species — never writes.

        Assembles context server-side (the merged dex entry + the real type pool),
        runs ONE bounded Port call, and returns the reusable
        ``{draft, rationale, alternatives}`` contract. The accept path is the
        existing ``PUT /api/species/{id}`` (the loader Boundary), not this route.

        Honest errors: a missing key / upstream failure (`LlmError`) → 503; an
        unknown species or a hallucinated type (`SuggestError`) → 422 — never a
        raw 500 traceback, and the provider key never reaches the client.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        chrooked_id, entry = _suggest_entry(snapshot, ruleset, chrooked_id, payload)
        type_pool = dexmod.build_type_pool(snapshot, ruleset)
        body = payload or {}
        direction = body.get("direction")
        # The makeover opening move rides this same Seam: `mode: "lore-options"`
        # returns 2-3 lore-grounded typing+role directions (`draft.options`)
        # instead of a single typing draft. Not a second prompt path (One Seam).
        mode = body.get("mode", "typing")
        # Both modes read real lore now (#79). Anything unrecognized normalizes to
        # off, so a typo in the body never starts a network fetch.
        lore_mode = suggestmod.normalize_lore_mode(body.get("lore"))
        try:
            if mode == "lore-options":
                response = suggestmod.suggest_lore_options(
                    provider=_llm_provider(),
                    entry=entry,
                    type_pool=type_pool,
                    direction=direction,
                    # KEPT facets (à la carte): the SPA sends the species' current
                    # values for facets set to KEEP so the options honor them.
                    kept_types=body.get("kept_types"),
                    kept_abilities=body.get("kept_abilities"),
                    lore_mode=lore_mode,
                    lore_provider=_lore_provider(snapshot, lore_mode),
                )
                _record_lore(chrooked_id, "lore-options", response)
                return response
            response = suggestmod.suggest_typing(
                provider=_llm_provider(),
                entry=entry,
                type_pool=type_pool,
                direction=direction,
                lore_mode=lore_mode,
                lore_provider=_lore_provider(snapshot, lore_mode),
            )
            _record_lore(chrooked_id, "typing", response)
            return response
        except suggestmod.SuggestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/api/species/{chrooked_id}/suggest/learnset")
    def suggest_species_learnset(
        chrooked_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Propose a full level-up learnset (or surgical edit) for a species — never writes.

        Assembles context server-side (the merged dex entry, the full merged move
        pool, and the merged abilities with effect text), runs ONE bounded Port call,
        and returns the reusable ``{draft, rationale, alternatives}`` contract. The
        accept path is the existing ``PUT /api/species/{id}`` (the loader Boundary);
        the `reasoning` field in each learnset row is proposal-only — strip it before
        PUT (the loader stores only `level` + `move`).

        Modes:
        - ``full`` (default): propose a whole learnset from scratch.
        - ``surgical``: change only the targeted move(s); requires `instruction`.

        Honest errors: a missing key / upstream failure (`LlmError`) → 503; an
        unknown species, a hallucinated move, an invalid level, a repeat-move
        violation, a surgical untouched-rows guard failure, or a missing instruction
        in surgical mode (`SuggestError`) → 422 — never a raw 500 traceback.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        chrooked_id, entry = _suggest_entry(snapshot, ruleset, chrooked_id, payload)
        move_pool = dexmod.build_move_pool(snapshot, ruleset)
        abilities = dexmod.build_abilities(snapshot, ruleset)
        body = payload or {}
        mode = body.get("mode", "full")
        instruction = body.get("instruction")
        direction = body.get("direction")
        anchors = body.get("anchors")
        # Researched lore, opted into per call. Anything unrecognized normalizes
        # to off, so a typo in the body never starts a network fetch.
        lore_mode = suggestmod.normalize_lore_mode(body.get("lore"))
        try:
            response = suggestmod.suggest_learnset(
                provider=_llm_provider(),
                entry=entry,
                move_pool=move_pool,
                abilities=abilities,
                mode=mode,
                instruction=instruction,
                direction=direction,
                anchors=anchors,
                lore_mode=lore_mode,
                lore_provider=_lore_provider(snapshot, lore_mode),
            )
            _record_lore(chrooked_id, "learnset", response)
            return response
        except suggestmod.SuggestError as error:
            # A draft that only tripped a soft shape bound is fully editable — hand
            # it back as a 200 (with an `error` note) so the author can fix it in
            # place. Only an unsalvageable failure is a bare 422.
            if error.salvage is not None:
                return error.salvage
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/api/species/{chrooked_id}/suggest/stats")
    def suggest_species_stats(
        chrooked_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Propose a six-stat spread for a species — never writes.

        Assembles context server-side (the merged dex entry including current stats
        and BST), runs ONE bounded Port call, and returns the reusable
        ``{draft, rationale, alternatives}`` contract. Honors a freeform direction
        or audits the current spread when none is given. The accept path is the
        existing ``PUT /api/species/{id}`` (the loader Boundary), not this route.

        Honest errors: a missing key / upstream failure (`LlmError`) → 503; an
        unknown species or an out-of-range stat (`SuggestError`) → 422 — never a
        raw 500 traceback, and the provider key never reaches the client.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        chrooked_id, entry = _suggest_entry(snapshot, ruleset, chrooked_id, payload)
        direction = (payload or {}).get("direction")
        try:
            return suggestmod.suggest_stats(
                provider=_llm_provider(),
                entry=entry,
                direction=direction,
            )
        except suggestmod.SuggestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.delete("/api/species/{chrooked_id}")
    def delete_species(chrooked_id: str, scope: str = "base") -> dict[str, str]:
        try:
            crudmod.delete_species(
                _scope_dir(scope), chrooked_id, ledger_dir=ruleset_dir, scope=scope
            )
        except crudmod.ValidationError as error:
            raise _422(error) from error
        except crudmod.NotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"deleted": chrooked_id}

    @app.put("/api/moves/{chrooked_id}")
    def put_move(
        chrooked_id: str, payload: dict[str, Any], scope: str = "base"
    ) -> dict[str, Any]:
        try:
            return crudmod.upsert_move(
                _scope_dir(scope), chrooked_id, payload, ledger_dir=ruleset_dir, scope=scope
            )
        except crudmod.ValidationError as error:
            raise _422(error) from error

    @app.delete("/api/moves/{chrooked_id}")
    def delete_move(chrooked_id: str, confirm: bool = False) -> dict[str, str]:
        return _delete_owned(crudmod.delete_move, chrooked_id, confirm)

    @app.post("/api/moves/suggest")
    def suggest_move_design(
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Draft a new owned move (create) or propose edits to an existing one (edit).

        Accepts a freeform ``direction`` (specifics / comparative / vibe) and
        an optional ``mode`` (``"create"`` or ``"edit"``; defaults to
        ``"create"``). In ``"edit"`` mode a ``move_id`` (chrooked_id of the
        existing move) is also required.

        Context assembled server-side: the merged type pool (so the model picks
        only real types), and the owned move ids (for the CREATE collision check).
        In edit mode the existing move's current field values are included so the
        model can produce a targeted delta and the before/after is built here.

        Returns the reusable ``{draft, rationale, alternatives}`` contract, plus:
        - ``chrooked_id``: the resolved id for the accept PUT path.
        - ``warnings``: any non-fatal validation notes (e.g. dropped unknown flags).
        - ``before``: (edit mode only) original values for the changed fields.

        The accept path is the existing ``PUT /api/moves/{id}`` (and optionally
        ``PUT /api/behaviors/{id}`` if the draft includes a custom behavior stub)
        — there is NO new write route here.

        Honest errors: a bad shape, an empty name, an id collision, a non-empty
        engine_hints, an unrecognized type, or an invalid numeric range
        (``SuggestError``) → 422; a missing key / upstream failure (``LlmError``)
        → 503 — never a raw 500 traceback, and the provider key never reaches
        the client.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        type_pool = dexmod.build_type_pool(snapshot, ruleset)
        move_ids = set(ruleset.moves)
        body = payload or {}
        direction = body.get("direction", "")
        mode = body.get("mode", "create")
        move_id = body.get("move_id")

        existing_move: dict[str, Any] | None = None
        if mode == "edit":
            if not move_id:
                raise HTTPException(
                    status_code=422,
                    detail="Edit mode requires a move_id (the chrooked_id of the move to edit).",
                )
            # Resolve existing move from the merged move pool.
            move_pool = dexmod.build_move_pool(snapshot, ruleset)
            all_moves = dexmod.build_moves(snapshot, ruleset)
            existing_move = next(
                (m for m in all_moves if m.get("chrooked_id") == move_id), None
            )
            if existing_move is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No move with chrooked_id {move_id!r} found.",
                )

        try:
            return suggestmod.suggest_move(
                provider=_llm_provider(),
                direction=direction,
                type_pool=type_pool,
                move_ids=move_ids,
                mode=mode,
                existing_move=existing_move,
            )
        except suggestmod.SuggestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/api/moves/{chrooked_id}/distribute")
    def distribute_move_recipients(
        chrooked_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Propose recipients + gap-placed levels for distributing a move; never writes.

        Two recipient modes (the body carries exactly one):
        - ``rule``: ``{types[], split, include_legendaries?, include_megas?}`` —
          deterministic selection by type + attack split.
        - ``prompt``: a freeform instruction (mechanical OR thematic) — the LLM
          Port chooses WHICH species fit; level placement stays deterministic.

        Shared body fields: ``levels`` (``[min, max]``) or ``preset``
        (early/mid/late) for the window; ``include_evolutions`` (default true) to
        pull each recipient's whole evolution line; ``evolved_at_1`` to park
        evolutions at level 1 instead of gap-placing them.

        Returns ``{rows, rationale, warnings, window, move}`` — read-only. Each row
        is ``{chrooked_id, name, dex, level, stage, line_id, matched, already_has}``.
        The accept path is the existing per-species ``PUT /api/species/{id}``.

        Honest errors: unknown move → 404; missing/invalid mode or split → 422;
        a thematic pick that names nothing real (SuggestError) → 422; LLM key /
        upstream failure (LlmError) → 503.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        dex = dexmod.build_dex(snapshot, ruleset)
        move = next(
            (m for m in dexmod.build_moves(snapshot, ruleset)
             if m.get("chrooked_id") == chrooked_id),
            None,
        )
        if move is None:
            raise HTTPException(
                status_code=404, detail=f"No move with chrooked_id {chrooked_id!r}."
            )

        body = payload or {}
        levels = body.get("levels")
        window = distmod.parse_window(
            levels=tuple(levels) if isinstance(levels, list) and len(levels) == 2 else None,
            preset=body.get("preset"),
        )
        include_evolutions = body.get("include_evolutions", True)
        evolved_at_1 = body.get("evolved_at_1", False)
        rarity = body.get("rarity", "common")
        if rarity not in distmod.RARITY:
            raise HTTPException(status_code=422, detail=f"Unknown rarity {rarity!r}.")
        # Size budget (evolution families), chosen BEFORE the request; clamped so a
        # bad/missing value never becomes an unbounded ask (the bug this fixes).
        limit = suggestmod.clamp_distribution_limit(body.get("limit"))

        records = {
            e["chrooked_id"]: distmod.SpeciesRecord(
                chrooked_id=e["chrooked_id"],
                name=e.get("name", e["chrooked_id"]),
                dex=e.get("dex"),
                types=tuple(e.get("types") or []),
                atk=(e.get("stats") or {}).get("atk", 0),
                spa=(e.get("stats") or {}).get("spa", 0),
                levels=tuple(m.get("level") for m in (e.get("learnset") or [])),
                bst=sum((e.get("stats") or {}).values()),
                has_move=any(m.get("move") == move["name"] for m in (e.get("learnset") or [])),
            )
            for e in dex
            if e.get("chrooked_id")
        }
        evo = distmod.build_evolution_index(snapshot["species"])

        # Rule (type + split) and prompt now COMBINE: a rule narrows the
        # candidate pool deterministically, and a prompt refines WITHIN it
        # (e.g. Fighting physical AND "has feet/legs"). At least one side is
        # required. A type makes the rule meaningful; split alone does not.
        prompt = (body.get("prompt") or "").strip() if isinstance(body.get("prompt"), str) else ""
        rule = body.get("rule") if isinstance(body.get("rule"), dict) else None
        rule_types = {t for t in (rule.get("types") or [])} if rule else set()
        split = (rule.get("split") if rule else None) or "physical"
        if rule and split not in distmod.SPLITS:
            raise HTTPException(status_code=422, detail=f"Unknown attack split {split!r}.")
        if not (rule_types or prompt):
            raise HTTPException(
                status_code=422,
                detail="Provide a type (with optional attack split) and/or a prompt.",
            )

        def _ruled_ids() -> list[str]:
            return distmod.select_by_rule(
                records.values(), types=rule_types, split=split,
                include_legendaries=(rule or {}).get("include_legendaries", False),
                include_megas=(rule or {}).get("include_megas", False),
            )

        rationale, warnings = "", []
        try:
            if prompt:
                # A type rule pre-filters the pool so the prompt refines within it;
                # without a type, the prompt ranges over the whole roster.
                if rule_types:
                    allowed = set(_ruled_ids())
                    pool = [e for e in dex if e["chrooked_id"] in allowed]
                    constraint = (
                        f"Pre-filtered to types: {', '.join(sorted(rule_types))}; "
                        f"attack split: {split}. Pick only from the roster shown."
                    )
                else:
                    pool, constraint = dex, ""
                sel = suggestmod.suggest_distribution_species(
                    provider=_llm_provider(), move=move, species=pool, prompt=prompt,
                    rarity=rarity, constraint=constraint, limit=limit,
                )
                matched, rationale, warnings = sel["ids"], sel["rationale"], sel["warnings"]
            else:
                # Deterministic rule only; rarity narrows by BST.
                matched = distmod.apply_breadth(records, _ruled_ids(), rarity)
        except suggestmod.SuggestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

        # Cap the selection to the first `limit` evolution FAMILIES (best-first:
        # BST-ranked in rule mode, model-ranked in prompt mode). Members of an
        # accepted family are all kept; the first member of a new family past the
        # budget is where the cut lands. include_evolutions still fills each kept
        # family's line downstream.
        matched = _cap_to_families(matched, evo, limit)

        rows = distmod.distribute(
            records, evo, matched_ids=matched, window=window,
            include_evolutions=include_evolutions, evolved_at_1=evolved_at_1,
            level_bias=distmod.RARITY[rarity]["bias"],
        )
        return {
            "rows": [
                {
                    "chrooked_id": r.chrooked_id,
                    "name": r.name,
                    "dex": r.dex,
                    "level": r.level,
                    "stage": r.stage,
                    "line_id": r.line_id,
                    "matched": r.matched,
                    "already_has": r.already_has,
                }
                for r in rows
            ],
            "rationale": rationale,
            "warnings": warnings,
            "window": [window[0], window[1]],
            "move": {"chrooked_id": chrooked_id, "name": move["name"]},
        }

    @app.post("/api/moves/{chrooked_id}/distribute/apply")
    def apply_distribution(
        chrooked_id: str, payload: dict[str, Any], scope: str = "base"
    ) -> dict[str, Any]:
        """Write a whole distribution in ONE request: append the move to each
        listed species' learnset (append-only), preserving every other Override
        field. Replaces the per-species GET+PUT fan-out the UI used to do, so a
        90-species apply is one round-trip and one dex refetch, not ~180.

        Body: ``{rows: [{chrooked_id, level}]}``. Each row adds the move at
        ``level`` (1–100); an existing instance of this move is re-levelled in
        place (no duplicate). Returns ``{applied, failed, count}`` — a bad row
        (unknown species, out-of-range level, loader rejection) lands in
        ``failed`` with a reason and never aborts the rest. Unknown move → 404;
        empty rows → 422.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        move = next(
            (m for m in dexmod.build_moves(snapshot, ruleset)
             if m.get("chrooked_id") == chrooked_id),
            None,
        )
        if move is None:
            raise HTTPException(
                status_code=404, detail=f"No move with chrooked_id {chrooked_id!r}."
            )
        move_name = move["name"]

        rows = (payload or {}).get("rows")
        if not isinstance(rows, list) or not rows:
            raise HTTPException(status_code=422, detail="No rows to apply.")

        dex_by_id = {e["chrooked_id"]: e for e in dexmod.build_dex(snapshot, ruleset)}
        scope_dir = _scope_dir(scope)

        applied: list[str] = []
        failed: list[dict[str, str]] = []
        for row in rows:
            cid = row.get("chrooked_id") if isinstance(row, dict) else None
            level = row.get("level") if isinstance(row, dict) else None
            entry = dex_by_id.get(cid) if isinstance(cid, str) else None
            if entry is None:
                failed.append({"chrooked_id": str(cid), "error": "unknown species"})
                continue
            if not isinstance(level, int) or not 1 <= level <= 100:
                failed.append({"chrooked_id": cid, "error": "level must be 1–100"})
                continue

            raw = ruleset.species.get(cid)
            body = (
                crudmod.serialize_species(raw)
                if raw is not None
                else {
                    "name": entry.get("name", cid),
                    "chrooked_id": cid,
                    "aka": {"dex": entry["dex"]} if entry.get("dex") is not None else {},
                    "types": None, "abilities": None, "stats": None,
                    "learnset": None, "evolution": None,
                }
            )
            # Append-only: drop only THIS move (re-level), then re-add it. No
            # other learnset entry is ever removed.
            current = entry.get("learnset") or []
            kept = [m for m in current if m.get("move") != move_name]
            body["learnset"] = [*kept, {"level": level, "move": move_name}]

            try:
                crudmod.upsert_species(
                    scope_dir, cid, body, ledger_dir=ruleset_dir, scope=scope
                )
                applied.append(cid)
            except crudmod.ValidationError as error:
                failed.append({"chrooked_id": cid, "error": str(error)})

        return {"applied": applied, "failed": failed, "count": len(applied)}

    @app.put("/api/abilities/{chrooked_id}")
    def put_ability(
        chrooked_id: str, payload: dict[str, Any], scope: str = "base"
    ) -> dict[str, Any]:
        try:
            return crudmod.upsert_ability(
                _scope_dir(scope), chrooked_id, payload, ledger_dir=ruleset_dir, scope=scope
            )
        except crudmod.ValidationError as error:
            raise _422(error) from error

    @app.put("/api/statuses/{chrooked_id}")
    def put_status(
        chrooked_id: str, payload: dict[str, Any], scope: str = "base"
    ) -> dict[str, Any]:
        try:
            return crudmod.upsert_status(
                _scope_dir(scope), chrooked_id, payload, ledger_dir=ruleset_dir, scope=scope
            )
        except crudmod.ValidationError as error:
            raise _422(error) from error

    @app.post("/api/abilities/suggest")
    def suggest_ability_creation(
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Draft a brand-new ability + behavior stub + distribution — never writes.

        The FIRST capability that *creates* owned content rather than picking from
        a pool. Assembles context server-side (the existing ability pool as the
        cache prefix, the owned-ability ∪ behavior id sets for the collision check,
        and a name→entry dex lookup so each distribution row is validated and its
        `replaces` enriched from the real current slot), runs ONE bounded Port call,
        and returns the reusable ``{draft, rationale, alternatives}`` contract.

        The accept path is the existing CRUD routes, client-orchestrated in order
        (``PUT /api/abilities/{id}`` → ``PUT /api/behaviors/{id}`` →
        ``PUT /api/species/{id}`` ×N) — there is NO new write route here.

        Honest errors: a bad shape, an empty name, an id collision, a non-empty
        engine_hints, a hallucinated species, or an invalid slot (`SuggestError`)
        → 422; a missing key / upstream failure (`LlmError`) → 503 — never a raw
        500 traceback, and the provider key never reaches the client.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        abilities = dexmod.build_abilities(snapshot, ruleset)
        ability_pool = suggestmod.build_ability_pool(abilities)
        # The collision set spans BOTH owned abilities and behaviors (D4): a new
        # ability id must not shadow either. Both are keyed by chrooked_id.
        ability_ids = set(ruleset.abilities)
        behavior_ids = set(ruleset.behaviors)
        # Name → merged dex entry: the model proposes species BY NAME, so the
        # distribution validation resolves + enriches by case-folded name.
        dex = dexmod.build_dex(snapshot, ruleset)
        dex_lookup = {entry["name"].strip().casefold(): entry for entry in dex}
        # The in-dex species roster (sorted, deterministic) is fed to the model
        # so its distribution picks land in-dex — the model knows ~1000 species
        # but this dex carries a subset (bounce-1 fix).
        roster = sorted(
            entry["name"] for entry in dex if entry.get("name")
        )
        direction = (payload or {}).get("direction", "")
        # The ANCHOR species (#79): present when this panel opened inside a
        # makeover, absent on the standalone create path. Anything unrecognized
        # normalizes to off, so a typo in the body never starts a network fetch.
        lore_mode = suggestmod.normalize_lore_mode((payload or {}).get("lore"))
        species_id = (payload or {}).get("species")
        anchor_entry = None
        if isinstance(species_id, str) and species_id.strip():
            resolved_id = dexmod.resolve_form_id(snapshot, species_id.strip())
            anchor_entry = dexmod.build_dex_entry(snapshot, ruleset, resolved_id)
        try:
            response = suggestmod.suggest_ability_creation(
                provider=_llm_provider(),
                direction=direction,
                ability_pool=ability_pool,
                ability_ids=ability_ids,
                behavior_ids=behavior_ids,
                dex_lookup=dex_lookup,
                roster=roster,
                entry=anchor_entry,
                lore_mode=lore_mode,
                lore_provider=_lore_provider(snapshot, lore_mode),
            )
            if anchor_entry is not None:
                _record_lore(anchor_entry["chrooked_id"], "ability-create", response)
            return response
        except suggestmod.SuggestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/api/abilities/{chrooked_id}/distribute")
    def distribute_ability_recipients(
        chrooked_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Propose recipient species + slots for an EXISTING ability; never writes.

        The ability twin of ``POST /api/moves/{id}/distribute``: the LLM Port
        chooses WHICH in-dex species should carry this ability and in which slot,
        from a freeform prompt (the route falls back to the ability's own
        description when the caller gives none, so a one-click ✦ Suggest works).
        Returns ``{rows, rationale, warnings}`` — read-only. The accept path is the
        existing per-species ``PUT /api/species/{id}`` (through the panel's
        confirm). A hallucinated species is DROPPED into ``warnings`` (never
        guessed), mirroring the ability-creation distribution validation.

        Honest errors: unknown ability → 404; an empty prompt AND empty ability
        (``SuggestError``) → 422; LLM key / upstream failure (``LlmError``) → 503.
        """
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        abilities = dexmod.build_abilities(snapshot, ruleset)
        ability = next(
            (a for a in abilities if a.get("chrooked_id") == chrooked_id), None
        )
        if ability is None:
            raise HTTPException(
                status_code=404,
                detail=f"No ability with chrooked_id {chrooked_id!r}.",
            )
        # Name → merged dex entry (the model proposes species BY NAME); the sorted
        # in-dex roster is fed to the model so its picks land in-dex (mirrors the
        # ability-creation route's context assembly).
        dex = dexmod.build_dex(snapshot, ruleset)
        dex_lookup = {entry["name"].strip().casefold(): entry for entry in dex}
        roster = sorted(entry["name"] for entry in dex if entry.get("name"))
        body = payload or {}
        prompt = body.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            # Fall back to the ability's own description (then name) as the
            # instruction so the opt-in ✦ Suggest needs no typed prompt.
            prompt = str(ability.get("description") or ability.get("name") or "")
        rarity = body.get("rarity", "common")
        # Size budget (evolution families), chosen BEFORE the request; clamped so a
        # bad/missing value never becomes an unbounded ask (the bug this fixes).
        limit = suggestmod.clamp_distribution_limit(body.get("limit"))
        try:
            result = suggestmod.suggest_ability_distribution(
                provider=_llm_provider(),
                ability=ability,
                dex_lookup=dex_lookup,
                roster=roster,
                prompt=prompt,
                rarity=rarity,
                limit=limit,
            )
        except suggestmod.SuggestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        # Hard family cap: the rubric only ASKS for at most `limit` families; a
        # broad prompt makes the model over-produce, so enforce the budget here so
        # the returned size actually matches what the author requested.
        evo = distmod.build_evolution_index(snapshot["species"])
        result["rows"] = _cap_ability_rows_to_families(
            result.get("rows", []), evo, limit
        )
        return result

    @app.delete("/api/abilities/{chrooked_id}")
    def delete_ability(chrooked_id: str, confirm: bool = False) -> dict[str, str]:
        return _delete_owned(crudmod.delete_ability, chrooked_id, confirm)

    @app.put("/api/type-chart")
    def put_type_chart(
        entries: list[dict[str, Any]], scope: str = "base"
    ) -> list[dict[str, Any]]:
        # The type chart is one whole-list file; a write replaces the override set.
        try:
            return crudmod.replace_type_chart(
                _scope_dir(scope), entries, ledger_dir=ruleset_dir, scope=scope
            )
        except crudmod.ValidationError as error:
            raise _422(error) from error

    @app.put("/api/behaviors/{chrooked_id}")
    def put_behavior(
        chrooked_id: str, payload: dict[str, Any], scope: str = "base"
    ) -> dict[str, Any]:
        try:
            return crudmod.upsert_behavior(
                _scope_dir(scope), chrooked_id, payload, ledger_dir=ruleset_dir, scope=scope
            )
        except crudmod.ValidationError as error:
            raise _422(error) from error

    @app.delete("/api/behaviors/{chrooked_id}")
    def delete_behavior(chrooked_id: str) -> dict[str, str]:
        try:
            crudmod.delete_behavior(ruleset_dir, chrooked_id, ledger_dir=ruleset_dir)
        except crudmod.NotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"deleted": chrooked_id}

    def _delete_owned(
        deleter: Callable[..., None], chrooked_id: str, confirm: bool
    ) -> dict[str, str]:
        """Shared delete path for moves/abilities: load, citation-guard, unlink.

        A still-cited reference is a 409 whose detail names the citing species so
        the UI can show exactly what would dangle; `confirm=true` overrides it.
        The citation check runs against the per-request Ruleset load — best-effort
        in the single-user local app; concurrent edits aren't serialized.
        """
        ruleset = _load_ruleset_or_503()
        try:
            deleter(ruleset, ruleset_dir, chrooked_id, confirm=confirm, ledger_dir=ruleset_dir)
        except crudmod.NotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except crudmod.CitationError as error:
            raise HTTPException(
                status_code=409,
                detail={"message": str(error), "citing": error.citing},
            ) from error
        return {"deleted": chrooked_id}

    # --- Targets, preview, apply (Milestone 3) ------------------------------ #
    # A Target is a registered game fork the Ruleset is applied to. Preview runs
    # the real applier then restores the fork; apply keeps the changes. All target
    # state hangs off app.state so each app instance is isolated.

    def _target_error(error: targetsmod.TargetError) -> HTTPException:
        return HTTPException(status_code=error.status, detail=error.detail)

    def _unexpected_target_error(
        operation: str, target_id: str, error: Exception
    ) -> HTTPException:
        """Turn an unexpected crash into an honest 500 instead of an opaque page.

        A non-``TargetError`` failure (e.g. the applier crashing mid-run) would
        otherwise reach the client as Starlette's plain "Internal Server Error"
        with no JSON body. Log the full traceback server-side, surface the cause
        and what failed to the client.
        """
        _logger.exception(
            "Unexpected error during %s of target %r", operation, target_id
        )
        # ponytail: surface the real message verbatim (type + str) — this is a
        # localhost single-user tool whose whole point is honest, debuggable
        # errors (PRODUCT.md). The full traceback is logged above. Sanitize the
        # detail only if this app is ever hosted for someone other than its dev.
        return HTTPException(
            status_code=500,
            detail=(
                f"The {operation} of target {target_id!r} failed "
                f"({type(error).__name__}): {error}"
            ),
        )

    @app.get("/api/targets")
    def list_targets() -> list[dict[str, Any]]:
        return [t.as_dict() for t in app.state.targets_registry.list()]

    @app.post("/api/targets")
    def add_target(payload: dict[str, Any]) -> dict[str, Any]:
        # Boundary guard: `path`/`label` must be non-empty strings. A null/missing
        # path would otherwise reach `Path(None)` and 500; reject it as a 422 with
        # a clear message before touching the registry.
        label = payload.get("label")
        path = payload.get("path")
        for field, value in (("label", label), ("path", path)):
            if not isinstance(value, str) or not value.strip():
                raise HTTPException(
                    status_code=422,
                    detail=f"Field {field!r} is required and must be a non-empty string.",
                )
        try:
            target = app.state.targets_registry.add(
                label=label,
                path=path,
                engine=payload.get("engine", "pokeemerald"),
                namespace=payload.get("namespace"),
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        return target.as_dict()

    @app.put("/api/targets/{target_id}/namespace")
    def set_target_namespace(
        target_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Bind (or clear) a Target's override namespace. Body: ``{"slug": "africanvs"}``."""
        slug = (payload or {}).get("slug")
        try:
            return app.state.targets_registry.set_namespace(target_id, slug).as_dict()
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.get("/api/targets/{target_id}/namespace")
    def get_target_namespace(target_id: str) -> dict[str, Any]:
        """The active namespace for a Target: ``{slug, engine, label}`` or 404."""
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        if not target.namespace:
            raise HTTPException(
                status_code=404, detail=f"Target {target_id!r} has no override namespace."
            )
        return {"slug": target.namespace, "engine": target.engine, "label": target.label}

    @app.delete("/api/targets/{target_id}")
    def delete_target(target_id: str) -> dict[str, str]:
        try:
            app.state.targets_registry.remove(target_id)
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        return {"deleted": target_id}

    @app.post("/api/pick-directory")
    def pick_directory() -> dict[str, str | None]:
        """Open the host's native folder picker; return {path} (null = cancelled).

        Localhost-only convenience: the browser can't give the server a real
        filesystem path, so the server pops the OS dialog. 501 when the host has
        no picker we can drive — the form then falls back to typing the path.
        """
        try:
            return {"path": pickermod.pick_directory()}
        except pickermod.PickerUnavailable as error:
            raise HTTPException(status_code=501, detail=str(error)) from error

    @app.post("/api/targets/{target_id}/preview")
    def preview_target(target_id: str) -> dict[str, Any]:
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            effective, _ = _effective(target)
            return targetsmod.preview_target(
                target, effective, app.state.targets_state,
                ruleset_dir=ruleset_dir,
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        except Exception as error:  # applier crash etc. — keep the 500 honest
            raise _unexpected_target_error("preview", target_id, error) from error

    @app.post("/api/targets/{target_id}/apply")
    def apply_target(
        target_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        force = bool((payload or {}).get("force", False))
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            effective, _ = _effective(target)
            return targetsmod.apply_target(
                target,
                effective,
                app.state.targets_state,
                force=force,
                ledger_dir=ruleset_dir,
                ruleset_dir=ruleset_dir,
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        except Exception as error:  # applier crash etc. — keep the 500 honest
            raise _unexpected_target_error("apply", target_id, error) from error

    @app.post("/api/targets/{target_id}/read-back")
    def read_back_target(
        target_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Diff a Target's applied on-disk species against the Ruleset expectation.

        In-Game Proof for the workbench tail: after an apply, read each changed
        species back off the Target's fresh snapshot and diff it field-by-field
        against the merged canon dex entry (the Ruleset's expectation). A green
        Apply Report is not proof — this catches form-join/clobber bugs that ship
        past it. Body: ``{chrooked_ids: [...]}``; only the fields the Ruleset
        actually overrode are asserted. Returns the ``read_back`` proof artifact.
        """
        chrooked_ids = (payload or {}).get("chrooked_ids") or []
        if not isinstance(chrooked_ids, list) or not chrooked_ids:
            raise HTTPException(
                status_code=422,
                detail="read-back needs a non-empty `chrooked_ids` list.",
            )
        registry = app.state.targets_registry
        snapshot = _load_snapshot_or_503()
        ruleset = _load_ruleset_or_503()
        try:
            target = registry.get(target_id)
            # A fresh parse of the Target's on-disk state (apply invalidates the
            # cache, so this reflects what actually landed).
            target_snapshot = app.state.targets_state.snapshot_for(target)
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        target_species = target_snapshot.get("species", {})
        # Display-name → aka hints, so an explicit engine symbol wins over the
        # derived one when the read-back compares in resolution space (ac: names
        # are engine symbols on disk, display names in the Ruleset).
        aka_by_name: dict[str, dict[str, Any]] = {}
        for entry in (*dexmod.build_abilities(snapshot, ruleset), *dexmod.build_moves(snapshot, ruleset)):
            name = entry.get("name")
            if name and entry.get("aka"):
                aka_by_name[str(name).casefold()] = entry["aka"]
        results: list[dict[str, Any]] = []
        backdrop_by_id: dict[str, dict[str, Any]] | None = None
        for cid in chrooked_ids:
            expected = dexmod.build_dex_entry(snapshot, ruleset, cid)
            if expected is None:
                # A Target-original form (Rejuv's `breloom--aevianform`) has no
                # canon entry; its expected state is the backdrop merge (target ⊕
                # effective Ruleset) — the same join the workbench designed it
                # on. Built once, and only when a cid actually needs it.
                if backdrop_by_id is None:
                    effective, overlay = _display_effective(target)
                    backdrop_by_id = {
                        e["chrooked_id"]: e
                        for e in targetsmod.target_dex(
                            target,
                            effective,
                            app.state.targets_state,
                            base_snapshot=snapshot,
                            overlay=overlay,
                        )
                    }
                expected = backdrop_by_id.get(cid)
            if expected is None:
                continue
            fields = [
                f
                for f in expected.get("overridden_fields", [])
                if f in readbackmod.COMPARABLE_FIELDS
            ] or list(readbackmod.COMPARABLE_FIELDS)
            results.append(
                readbackmod.diff_species(
                    expected,
                    target_species.get(cid),
                    fields=fields,
                    aka_by_name=aka_by_name,
                )
            )
        return readbackmod.read_back(results)

    @app.get("/api/targets/{target_id}/dex")
    def get_target_dex(target_id: str) -> list[dict[str, Any]]:
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            effective, overlay = _display_effective(target)
            return targetsmod.target_dex(
                target,
                effective,
                app.state.targets_state,
                base_snapshot=_load_snapshot_or_503(),
                overlay=overlay,
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.get("/api/targets/{target_id}/abilities")
    def get_target_abilities(target_id: str) -> list[dict[str, Any]]:
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            effective, _ = _display_effective(target)
            return targetsmod.target_abilities(
                target,
                effective,
                app.state.targets_state,
                base_snapshot=_load_snapshot_or_503(),
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.get("/api/targets/{target_id}/moves")
    def get_target_moves(target_id: str) -> list[dict[str, Any]]:
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            effective, _ = _display_effective(target)
            return targetsmod.target_moves(
                target,
                effective,
                app.state.targets_state,
                base_snapshot=_load_snapshot_or_503(),
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.get("/api/targets/{target_id}/type-chart")
    def get_target_type_chart(target_id: str) -> list[dict[str, Any]]:
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            effective, _ = _display_effective(target)
            return targetsmod.target_type_chart(
                target, effective, app.state.targets_state
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.get("/api/targets/{target_id}/dialect")
    def get_target_dialect(target_id: str) -> dict[str, str | None]:
        """Return the detected Essentials PBS dialect for a registered Target.

        Calls ``detect_dialect`` fresh on each request so the result reflects
        the current on-disk state of the target. pokeemerald Targets return
        ``{dialect: null, label: null}``.
        """
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            return targetsmod.target_dialect(target)
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.get("/api/targets/{target_id}/save-status")
    def get_target_save_status(target_id: str) -> dict[str, Any]:
        """Save-state sync health for the shared saves folder (#88).

        Telemetry, not an operation: an unreachable Syncthing or an unmounted
        saves dir returns ``{"available": false}`` so the drawer can stay quiet.
        The target id is validated so the route 404s on a stale drawer, but the
        payload is machine-wide — one saves folder, not one per target.
        """
        registry = app.state.targets_registry
        try:
            registry.get(target_id)
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        return save_sync.save_status()

    def _crop_quadrant(sprite_path: Path) -> bytes:
        """Top-left quadrant of a 2x2 battler sheet as PNG bytes (lru-cached)."""
        return _crop_quadrant_cached(str(sprite_path), sprite_path.stat().st_mtime_ns)

    @lru_cache(maxsize=512)
    def _crop_quadrant_cached(path: str, _mtime: int) -> bytes:
        from io import BytesIO

        from PIL import Image

        with Image.open(path) as sheet:
            quadrant = sheet.crop((0, 0, sheet.width // 2, sheet.height // 2))
            buffer = BytesIO()
            quadrant.save(buffer, format="PNG")
            return buffer.getvalue()

    @app.get("/api/targets/{target_id}/sprite/{dex}")
    def get_target_sprite(target_id: str, dex: int, id: str | None = None) -> FileResponse:
        """Serve a target game's own front-battle sprite.

        ``dex`` is an ``int`` path param — FastAPI rejects non-int inputs with 422,
        which closes the path-traversal vector. Essentials targets resolve
        ``Graphics/Battlers/Front/<dex>.png``. Rejuv targets resolve by the
        ``id`` query param (the entry's chrooked_id) through the cached snapshot's
        per-form sprite hint: ``Graphics/Battlers/<species>/<form>.png`` — so a
        form entry (Aevian, Mega) shows its own art. The resolved path is
        asserted to stay under Graphics/Battlers (defense in depth); a missing
        file or unsupported engine yields 404 (the UI falls back to the CDN).
        """
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        battlers_dir = (Path(target.path) / "Graphics" / "Battlers").resolve()
        if target.engine == "essentials":
            sprite_path = (battlers_dir / "Front" / f"{dex:03d}.png").resolve()
        elif target.engine == "rejuv" and id:
            snapshot = app.state.targets_state.snapshot_for(target)
            entry = snapshot["species"].get(id)
            hint = (entry or {}).get("sprite")
            if not hint:
                raise HTTPException(status_code=404, detail="Sprite not found.")
            sprite_path = (battlers_dir / hint["folder"] / f"{hint['form']}.png").resolve()
        else:
            raise HTTPException(status_code=404, detail="Sprite endpoint requires an Essentials or Rejuv target.")
        if not str(sprite_path).startswith(str(battlers_dir) + "/"):
            raise HTTPException(status_code=404, detail="Sprite not found.")
        if not sprite_path.is_file():
            raise HTTPException(status_code=404, detail=f"No sprite for dex {dex}.")
        if target.engine == "rejuv":
            # Rejuv battlers are 2x2 sheets (front/back x normal/shiny); serve
            # the front-normal quadrant (top-left) so the dex shows one sprite.
            return Response(content=_crop_quadrant(sprite_path), media_type="image/png")
        return FileResponse(str(sprite_path), media_type="image/png")

    @app.get("/api/behaviors/{chrooked_id}/packet")
    def get_behavior_packet(
        chrooked_id: str, engine: str = "pokeemerald"
    ) -> dict[str, str]:
        ruleset = _load_ruleset_or_503()
        spec = ruleset.behavior_for(chrooked_id)
        if spec is None:
            raise HTTPException(
                status_code=404,
                detail=f"No behavior spec for {chrooked_id!r}.",
            )
        return {"chrooked_id": chrooked_id, "markdown": render_packet(spec, engine)}

    if dist_dir is not None and Path(dist_dir).exists():
        app.mount("/", _SpaFiles(directory=str(dist_dir), html=True), name="frontend")

    return app


class _SpaFiles(StaticFiles):
    """StaticFiles that never lets a browser cache ``index.html``.

    The build fingerprints every asset (``index-<hash>.js``), so those are safe
    to cache forever — but only if the HTML naming them is re-fetched. Served
    without a ``Cache-Control`` header, ``index.html`` falls under heuristic
    freshness: the browser may reuse a stored copy for a while WITHOUT
    revalidating, keep asking for the asset hashes that copy names, and so keep
    running an old build indefinitely.

    That is not theoretical here. The handheld this app is used from sat on a
    stale index.html across several deploys, showing an old bundle while the
    server had the new one — a fix looks like it did nothing, which is the
    worst possible failure to debug remotely.

    ``no-cache`` does not mean "do not store"; it means "revalidate before
    reuse", so the usual 304 still applies and only the tiny HTML is rechecked.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        # `html=True` rewrites a directory or unknown path to index.html, so
        # match on what actually gets served rather than on the request path.
        if path in ("", ".", "/", "index.html") or path.endswith("/index.html"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        elif path.startswith("assets/"):
            # The other half of the same contract. A hashed name never changes
            # content, so revalidating it is pure cost; without a header these
            # fall under the same heuristic freshness as the HTML and the
            # handheld re-fetches a 650 KB bundle on someone else's timetable.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_app_from_env() -> FastAPI:
    """Factory for `uvicorn --reload` (the CLI's `ui --reload`).

    Reload runs the app in a worker subprocess that re-imports this module on
    every code change, so it can't receive the CLI's parsed paths directly — it
    reads them from environment variables the CLI sets before launching uvicorn.
    """
    # Load a repo-root `.env` first so provider keys/config (ANTHROPIC_API_KEY,
    # LLM_MODEL, …) reach this worker's process env. A real env var always wins;
    # a missing .env / python-dotenv is a no-op.
    load_env_file()

    ruleset = os.environ.get("CHROOKED_RULESET")
    snapshot = os.environ.get("CHROOKED_SNAPSHOT")
    dist = os.environ.get("CHROOKED_DIST")
    return create_app(
        ruleset_dir=Path(ruleset) if ruleset else Path("ruleset"),
        snapshot_path=Path(snapshot) if snapshot else snapmod.DEFAULT_SNAPSHOT_PATH,
        dist_dir=Path(dist) if dist else None,
    )
