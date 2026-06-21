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
import os
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..behavior import render_packet
from ..env import load_env_file
from ..model import Ruleset
from . import collections as colmod
from . import crud as crudmod
from . import dex as dexmod
from . import llm as llmmod
from . import snapshot as snapmod
from . import suggest as suggestmod
from . import targets as targetsmod

# The Target registry lives at the project root by default (D4): a gitignored
# `targets.json` holding machine-specific fork paths, never canon.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_TARGETS_PATH = _PROJECT_ROOT / "targets.json"


def create_app(
    *,
    ruleset_dir: Path,
    snapshot_path: Path = snapmod.DEFAULT_SNAPSHOT_PATH,
    dist_dir: Path | None = None,
    targets_path: Path | None = None,
    llm_provider: llmmod.LlmProvider | None = None,
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

    # Per-app Target state on app.state for clean test isolation: the registry
    # path, a per-fork lock registry, and the per-Target snapshot cache (D2/D4).
    app.state.targets_registry = targetsmod.TargetRegistry(
        Path(targets_path) if targets_path is not None else DEFAULT_TARGETS_PATH
    )
    app.state.targets_state = targetsmod.TargetState()

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
        snapshot = _load_snapshot_or_503()
        return dexmod.build_dex(snapshot, _load_ruleset_or_503())

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

    @app.get("/api/type-chart")
    def get_type_chart() -> list[dict[str, Any]]:
        # Canon type chart reaches parity: the full base matrix ⊕ Ruleset, merged
        # per-cell like the dex (was the sparse Ruleset-only list before this slice).
        snapshot = _load_snapshot_or_503()
        return dexmod.build_type_chart(snapshot, _load_ruleset_or_503())

    @app.get("/api/behaviors")
    def get_behaviors() -> list[dict[str, Any]]:
        return colmod.build_behaviors(_load_ruleset_or_503())

    # --- Write routes (Milestone 2a): species / moves / abilities ----------- #
    # Each write validates by reloading through the loader; a rejected edit is a
    # 422 carrying the loader's own message and nothing is written. The UI never
    # commits — Chris reviews `git diff` himself.

    def _422(error: crudmod.ValidationError) -> HTTPException:
        return HTTPException(status_code=422, detail=str(error))

    @app.get("/api/species/{chrooked_id}")
    def get_species_override(chrooked_id: str) -> dict[str, Any]:
        # The raw Override (overrides-only), distinct from the merged /api/dex
        # entry — the species editor needs exactly the changed fields so a save
        # round-trips them without writing base values back as Overrides.
        ruleset = _load_ruleset_or_503()
        override = ruleset.species.get(chrooked_id)
        if override is None:
            raise HTTPException(
                status_code=404,
                detail=f"No species Override for {chrooked_id!r}.",
            )
        return crudmod.serialize_species(override)

    @app.put("/api/species/{chrooked_id}")
    def put_species(chrooked_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return crudmod.upsert_species(ruleset_dir, chrooked_id, payload)
        except crudmod.ValidationError as error:
            raise _422(error) from error

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
        entry = dexmod.build_dex_entry(snapshot, ruleset, chrooked_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"No species with chrooked_id {chrooked_id!r}."
            )
        abilities = dexmod.build_abilities(snapshot, ruleset)
        direction = (payload or {}).get("direction")
        try:
            return suggestmod.suggest_ability(
                provider=_llm_provider(),
                entry=entry,
                abilities=abilities,
                direction=direction,
            )
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
        entry = dexmod.build_dex_entry(snapshot, ruleset, chrooked_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"No species with chrooked_id {chrooked_id!r}."
            )
        type_pool = dexmod.build_type_pool(snapshot, ruleset)
        direction = (payload or {}).get("direction")
        try:
            return suggestmod.suggest_typing(
                provider=_llm_provider(),
                entry=entry,
                type_pool=type_pool,
                direction=direction,
            )
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
        entry = dexmod.build_dex_entry(snapshot, ruleset, chrooked_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"No species with chrooked_id {chrooked_id!r}."
            )
        move_pool = dexmod.build_move_pool(snapshot, ruleset)
        abilities = dexmod.build_abilities(snapshot, ruleset)
        body = payload or {}
        mode = body.get("mode", "full")
        instruction = body.get("instruction")
        direction = body.get("direction")
        try:
            return suggestmod.suggest_learnset(
                provider=_llm_provider(),
                entry=entry,
                move_pool=move_pool,
                abilities=abilities,
                mode=mode,
                instruction=instruction,
                direction=direction,
            )
        except suggestmod.SuggestError as error:
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
        entry = dexmod.build_dex_entry(snapshot, ruleset, chrooked_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"No species with chrooked_id {chrooked_id!r}."
            )
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
    def delete_species(chrooked_id: str) -> dict[str, str]:
        try:
            crudmod.delete_species(ruleset_dir, chrooked_id)
        except crudmod.NotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"deleted": chrooked_id}

    @app.put("/api/moves/{chrooked_id}")
    def put_move(chrooked_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return crudmod.upsert_move(ruleset_dir, chrooked_id, payload)
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

    @app.put("/api/abilities/{chrooked_id}")
    def put_ability(chrooked_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return crudmod.upsert_ability(ruleset_dir, chrooked_id, payload)
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
        try:
            return suggestmod.suggest_ability_creation(
                provider=_llm_provider(),
                direction=direction,
                ability_pool=ability_pool,
                ability_ids=ability_ids,
                behavior_ids=behavior_ids,
                dex_lookup=dex_lookup,
                roster=roster,
            )
        except suggestmod.SuggestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except llmmod.LlmError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.delete("/api/abilities/{chrooked_id}")
    def delete_ability(chrooked_id: str, confirm: bool = False) -> dict[str, str]:
        return _delete_owned(crudmod.delete_ability, chrooked_id, confirm)

    @app.put("/api/type-chart")
    def put_type_chart(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # The type chart is one whole-list file; a write replaces the override set.
        try:
            return crudmod.replace_type_chart(ruleset_dir, entries)
        except crudmod.ValidationError as error:
            raise _422(error) from error

    @app.put("/api/behaviors/{chrooked_id}")
    def put_behavior(chrooked_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return crudmod.upsert_behavior(ruleset_dir, chrooked_id, payload)
        except crudmod.ValidationError as error:
            raise _422(error) from error

    @app.delete("/api/behaviors/{chrooked_id}")
    def delete_behavior(chrooked_id: str) -> dict[str, str]:
        try:
            crudmod.delete_behavior(ruleset_dir, chrooked_id)
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
            deleter(ruleset, ruleset_dir, chrooked_id, confirm=confirm)
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

    @app.get("/api/targets")
    def list_targets() -> list[dict[str, str]]:
        return [t.as_dict() for t in app.state.targets_registry.list()]

    @app.post("/api/targets")
    def add_target(payload: dict[str, Any]) -> dict[str, str]:
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
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        return target.as_dict()

    @app.delete("/api/targets/{target_id}")
    def delete_target(target_id: str) -> dict[str, str]:
        try:
            app.state.targets_registry.remove(target_id)
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        return {"deleted": target_id}

    @app.post("/api/targets/{target_id}/preview")
    def preview_target(target_id: str) -> dict[str, Any]:
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            return targetsmod.preview_target(
                target, _load_ruleset_or_503(), app.state.targets_state
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.post("/api/targets/{target_id}/apply")
    def apply_target(
        target_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        force = bool((payload or {}).get("force", False))
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            return targetsmod.apply_target(
                target, _load_ruleset_or_503(), app.state.targets_state, force=force
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.get("/api/targets/{target_id}/dex")
    def get_target_dex(target_id: str) -> list[dict[str, Any]]:
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            return targetsmod.target_dex(
                target,
                _load_ruleset_or_503(),
                app.state.targets_state,
                base_snapshot=_load_snapshot_or_503(),
            )
        except targetsmod.TargetError as error:
            raise _target_error(error) from error

    @app.get("/api/targets/{target_id}/abilities")
    def get_target_abilities(target_id: str) -> list[dict[str, Any]]:
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
            return targetsmod.target_abilities(
                target,
                _load_ruleset_or_503(),
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
            return targetsmod.target_moves(
                target,
                _load_ruleset_or_503(),
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
            return targetsmod.target_type_chart(
                target, _load_ruleset_or_503(), app.state.targets_state
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

    @app.get("/api/targets/{target_id}/sprite/{dex}")
    def get_target_sprite(target_id: str, dex: int) -> FileResponse:
        """Serve a target game's own front-battle sprite for a given dex №.

        ``dex`` is an ``int`` path param — FastAPI rejects non-int inputs with 422,
        which closes the path-traversal vector. The resolved path is asserted to stay
        under the ``Graphics/Battlers/Front`` directory (defense in depth). A missing
        file or an unknown/non-essentials target yields 404.
        """
        registry = app.state.targets_registry
        try:
            target = registry.get(target_id)
        except targetsmod.TargetError as error:
            raise _target_error(error) from error
        if target.engine != "essentials":
            raise HTTPException(status_code=404, detail="Sprite endpoint requires an Essentials target.")
        front_dir = (Path(target.path) / "Graphics" / "Battlers" / "Front").resolve()
        sprite_path = (front_dir / f"{dex:03d}.png").resolve()
        # Assert the resolved path stays under the Front directory.
        if not str(sprite_path).startswith(str(front_dir) + "/") and sprite_path != front_dir:
            raise HTTPException(status_code=404, detail="Sprite not found.")
        if not sprite_path.is_file():
            raise HTTPException(status_code=404, detail=f"No sprite for dex {dex}.")
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
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

    return app


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
