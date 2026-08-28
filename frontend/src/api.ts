/* The thin fetch layer over the local FastAPI surface.

   Reads are unchanged from M1. M2a adds writes: PUT (upsert) and DELETE for the
   three simple-record kinds (species / moves / abilities), plus a raw-Override
   GET for the species editor.

   Errors carry the server's own message so the UI can surface it honestly — the
   loader's verbatim 422 text, a 409's citing-species list, the 503 "run
   snapshot" line — instead of a generic failure. `ApiError.detail` holds the
   parsed body so the 409 delete-guard can read its `citing` array. */

import type {
  Ability,
  AbilityProposal,
  AbilityWrite,
  ApplyReportSummary,
  ApplyDistributionResponse,
  ApplyDistributionRow,
  Behavior,
  Status,
  BehaviorPacket,
  CanonicalMethod,
  DexEntry,
  DistributeRequest,
  DistributeResponse,
  EngineKey,
  LearnsetProposal,
  LedgerEntry,
  LoreMode,
  Move,
  MoveWrite,
  SaveStatus,
  SpeciesOverride,
  Target,
  TargetDialect,
  TargetNamespace,
  TypeChartCell,
  TypeChartEntry,
} from "./types";
import { emitDataChange } from "./lib/dataChange";

/** The structured body of a blocked delete (HTTP 409). */
export interface CitationDetail {
  message: string;
  citing: string[];
}

export class ApiError extends Error {
  readonly status: number;
  /** The parsed `detail` payload: a string for most errors, a
      {@link CitationDetail} object for a 409 delete-guard block. */
  readonly detail: unknown;

  constructor(status: number, message: string, detail: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** The citing-species list from a 409 delete-guard error, or null otherwise. */
export function citingFrom(error: unknown): string[] | null {
  if (
    error instanceof ApiError &&
    error.status === 409 &&
    error.detail !== null &&
    typeof error.detail === "object" &&
    Array.isArray((error.detail as CitationDetail).citing)
  ) {
    return (error.detail as CitationDetail).citing;
  }
  return null;
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) {
    throw await toError(response);
  }
  return (await response.json()) as T;
}

export async function sendJson<T>(
  method: "POST" | "PUT" | "DELETE",
  path: string,
  payload?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers:
      payload !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    throw await toError(response);
  }
  return (await response.json()) as T;
}

async function toError(response: Response): Promise<ApiError> {
  let detail: unknown = null;
  try {
    const body = (await response.json()) as { detail?: unknown };
    detail = body.detail ?? null;
  } catch {
    // Non-JSON error body; fall through to the status line.
  }
  const message =
    typeof detail === "string"
      ? detail
      : detail !== null && typeof detail === "object" && "message" in detail
        ? String((detail as { message: unknown }).message)
        : `Request failed (${response.status} ${response.statusText})`;
  return new ApiError(response.status, message, detail);
}

function confirmQuery(confirm?: boolean): string {
  return confirm ? "?confirm=true" : "";
}

/** The edit-scope query: base (omitted) or a Target Override namespace. */
function scopeQuery(scope?: string): string {
  return scope && scope !== "base" ? `?scope=${encodeURIComponent(scope)}` : "";
}

/** Memoize a per-Target fetcher factory on the target id, so the SAME function
    object comes back every call. `useResource` keys its cross-mount cache on
    fetcher identity — a fresh closure per render would miss that cache and
    re-fetch every time a tab is opened. Ids are few and app-lifetime, so a plain
    Map is fine.
    ponytail: never evicted; targets are a handful per session. */
function byId<T>(
  make: (id: string) => (signal?: AbortSignal) => Promise<T>,
): (id: string) => (signal?: AbortSignal) => Promise<T> {
  const memo = new Map<string, (signal?: AbortSignal) => Promise<T>>();
  return (id: string) => {
    let fetcher = memo.get(id);
    if (fetcher === undefined) {
      fetcher = make(id);
      memo.set(id, fetcher);
    }
    return fetcher;
  };
}

export const api = {
  // Reads
  dex: (signal?: AbortSignal) => getJson<DexEntry[]>("/api/dex", signal),
  moves: (signal?: AbortSignal) => getJson<Move[]>("/api/moves", signal),
  abilities: (signal?: AbortSignal) => getJson<Ability[]>("/api/abilities", signal),
  typeChart: (signal?: AbortSignal) =>
    getJson<TypeChartCell[]>("/api/type-chart", signal),
  behaviors: (signal?: AbortSignal) => getJson<Behavior[]>("/api/behaviors", signal),
  statuses: (signal?: AbortSignal) => getJson<Status[]>("/api/statuses", signal),
  evolutionMethods: (signal?: AbortSignal) =>
    getJson<CanonicalMethod[]>("/api/meta/evolution-methods", signal),

  // Species (raw Override read + write)
  speciesOverride: (id: string, signal?: AbortSignal) =>
    getJson<SpeciesOverride>(`/api/species/${encodeURIComponent(id)}`, signal),
  putSpecies: (
    id: string,
    payload: SpeciesOverride,
    scope?: string,
    opts?: { silent?: boolean },
  ) =>
    sendJson<SpeciesOverride>(
      "PUT",
      `/api/species/${encodeURIComponent(id)}${scopeQuery(scope)}`,
      payload,
    ).then((result) => {
      // Species data changed → let the always-mounted dex resource refetch, so a
      // distribution/species edit made from any screen shows on the dex page.
      // `silent` lets a batch caller suppress the per-write signal and emit once
      // at the end (avoids an O(N) dex-refetch storm during a bulk save).
      if (!opts?.silent) emitDataChange();
      return result;
    }),
  /** Ask the LLM to propose an abilities block for this species (#6). A read-only
      action — proposes only, never writes. The `direction` is the author's
      freeform steer ("make it a special attacker"). Errors carry the server's
      own message (503 missing key / upstream, 422 invalid). */
  suggestAbility: (
    id: string,
    opts?: { direction?: string; locked?: string[]; lore?: LoreMode; target?: string },
  ) =>
    sendJson<AbilityProposal>(
      "POST",
      `/api/species/${encodeURIComponent(id)}/suggest/ability`,
      {
        direction: opts?.direction,
        locked: opts?.locked,
        lore: opts?.lore,
        // The backdrop Target this call was launched from — the server's
        // fallback join for a Target-original form canon has never heard of.
        target: opts?.target,
      },
    ),
  /** Ask the LLM to propose a whole learnset for this species (#7). Read-only —
      proposes only, never writes. `mode` defaults to a full-list proposal. */
  suggestLearnset: (
    id: string,
    opts?: {
      direction?: string;
      mode?: "full";
      anchors?: string[];
      lore?: LoreMode;
      target?: string;
    },
  ) =>
    sendJson<LearnsetProposal>(
      "POST",
      `/api/species/${encodeURIComponent(id)}/suggest/learnset`,
      {
        direction: opts?.direction,
        mode: opts?.mode ?? "full",
        // Omit the key entirely when empty — the server treats a missing
        // `anchors` and an empty one identically, and an absent key keeps the
        // request body honest about what the author actually asked for.
        anchors: opts?.anchors?.length ? opts.anchors : undefined,
        lore: opts?.lore,
        // The backdrop Target this call was launched from — the server's
        // fallback join for a Target-original form canon has never heard of.
        target: opts?.target,
      },
    ),
  deleteSpecies: (id: string, scope?: string) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/species/${encodeURIComponent(id)}${scopeQuery(scope)}`,
    ).then((result) => {
      emitDataChange();
      return result;
    }),

  // Moves
  putMove: (id: string, payload: MoveWrite, scope?: string) =>
    sendJson<MoveWrite>(
      "PUT",
      `/api/moves/${encodeURIComponent(id)}${scopeQuery(scope)}`,
      payload,
    ),
  deleteMove: (id: string, confirm?: boolean) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/moves/${encodeURIComponent(id)}${confirmQuery(confirm)}`,
    ),
  /** Propose recipients + gap-placed levels for distributing a move. Read-only —
      returns candidate rows, never writes. Body carries exactly one recipient
      mode (`rule` or `prompt`) plus the shared window/evolution options. Errors
      carry the server's message (422 invalid/empty, 503 LLM key/upstream). */
  distributeMove: (id: string, body: DistributeRequest) =>
    sendJson<DistributeResponse>(
      "POST",
      `/api/moves/${encodeURIComponent(id)}/distribute`,
      body,
    ),
  /** Write a whole distribution in ONE request (append-only). Replaces the
      per-species GET+PUT fan-out, then emits a single data-change so the dex
      refetches once. */
  applyDistribution: (id: string, rows: ApplyDistributionRow[]) =>
    sendJson<ApplyDistributionResponse>(
      "POST",
      `/api/moves/${encodeURIComponent(id)}/distribute/apply`,
      { rows },
    ).then((result) => {
      emitDataChange();
      return result;
    }),

  // Abilities
  putAbility: (id: string, payload: AbilityWrite, scope?: string) =>
    sendJson<AbilityWrite>(
      "PUT",
      `/api/abilities/${encodeURIComponent(id)}${scopeQuery(scope)}`,
      payload,
    ),
  deleteAbility: (id: string, confirm?: boolean) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/abilities/${encodeURIComponent(id)}${confirmQuery(confirm)}`,
    ),

  // Type chart (one whole-list file → a write replaces the override set)
  putTypeChart: (entries: TypeChartEntry[], scope?: string) =>
    sendJson<TypeChartEntry[]>("PUT", `/api/type-chart${scopeQuery(scope)}`, entries),

  // Statuses
  putStatus: (id: string, payload: Status, scope?: string) =>
    sendJson<Status>(
      "PUT",
      `/api/statuses/${encodeURIComponent(id)}${scopeQuery(scope)}`,
      payload,
    ),

  // Behaviors
  putBehavior: (id: string, payload: Behavior, scope?: string) =>
    sendJson<Behavior>(
      "PUT",
      `/api/behaviors/${encodeURIComponent(id)}${scopeQuery(scope)}`,
      payload,
    ),
  deleteBehavior: (id: string) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/behaviors/${encodeURIComponent(id)}`,
    ),

  // Targets (M3 — register a fork, preview/apply the Ruleset, read its backdrop)
  targets: (signal?: AbortSignal) => getJson<Target[]>("/api/targets", signal),
  /** Open the host's native folder picker; resolves to the chosen absolute path,
      or null if the user cancelled. 501 (ApiError) when the host has no picker. */
  pickDirectory: () =>
    sendJson<{ path: string | null }>("POST", "/api/pick-directory"),
  addTarget: (payload: { label: string; path: string; engine: EngineKey }) =>
    sendJson<Target>("POST", "/api/targets", payload),
  deleteTarget: (id: string) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/targets/${encodeURIComponent(id)}`,
    ),
  /** Safe: runs the real applier on the fork, then reverts it. 409 if dirty. */
  previewTarget: (id: string) =>
    sendJson<ApplyReportSummary>(
      "POST",
      `/api/targets/${encodeURIComponent(id)}/preview`,
    ),
  /** Destructive: writes the fork. 409 if dirty and `force` is not set. */
  applyTarget: (id: string, force?: boolean) =>
    sendJson<ApplyReportSummary>(
      "POST",
      `/api/targets/${encodeURIComponent(id)}/apply`,
      { force: force ?? false },
    ),
  /** The target's own values ⊕ Ruleset — the dex backdrop for that fork. */
  targetDex: byId((id) => (signal?: AbortSignal) =>
    getJson<DexEntry[]>(`/api/targets/${encodeURIComponent(id)}/dex`, signal),
  ),
  /** The target's abilities ⊕ Ruleset — the abilities backdrop for that fork. */
  targetAbilities: byId((id) => (signal?: AbortSignal) =>
    getJson<Ability[]>(
      `/api/targets/${encodeURIComponent(id)}/abilities`,
      signal,
    ),
  ),
  /** The target's moves ⊕ Ruleset — the moves backdrop for that fork. */
  targetMoves: byId((id) => (signal?: AbortSignal) =>
    getJson<Move[]>(`/api/targets/${encodeURIComponent(id)}/moves`, signal),
  ),
  /** The target's type chart ⊕ Ruleset — the type-chart backdrop for that fork. */
  targetTypeChart: byId((id) => (signal?: AbortSignal) =>
    getJson<TypeChartCell[]>(
      `/api/targets/${encodeURIComponent(id)}/type-chart`,
      signal,
    ),
  ),
  /** Fetch one behavior packet by its DATA-ONLY `packet_url`. */
  packet: (packetUrl: string, signal?: AbortSignal) =>
    getJson<BehaviorPacket>(packetUrl, signal),
  /** Detect the PBS dialect of an Essentials Target.
      pokeemerald Targets return { dialect: null, label: null }.
      Uses a fresh detect on each call so the badge never goes stale. */
  targetDialect: (id: string, signal?: AbortSignal) =>
    getJson<TargetDialect>(
      `/api/targets/${encodeURIComponent(id)}/dialect`,
      signal,
    ),
  /** Save-state sync health for the shared saves folder (#88). Never errors on
      an unreachable Syncthing — it returns { available: false }. */
  targetSaveStatus: (id: string, signal?: AbortSignal) =>
    getJson<SaveStatus>(
      `/api/targets/${encodeURIComponent(id)}/save-status`,
      signal,
    ),
  /** The Target's bound Override namespace ({slug, engine, label}), or 404. */
  targetNamespace: (id: string, signal?: AbortSignal) =>
    getJson<TargetNamespace>(
      `/api/targets/${encodeURIComponent(id)}/namespace`,
      signal,
    ),
  /** Bind (or clear) a Target's Override namespace slug. */
  setTargetNamespace: (id: string, slug: string | null) =>
    sendJson<Target>(
      "PUT",
      `/api/targets/${encodeURIComponent(id)}/namespace`,
      { slug },
    ),

  // Change Ledger (append-only history of every mutation)
  ledger: (
    opts?: { scope?: string; kind?: string; chrooked_id?: string; limit?: number },
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams();
    if (opts?.scope) params.set("scope", opts.scope);
    if (opts?.kind) params.set("kind", opts.kind);
    if (opts?.chrooked_id) params.set("chrooked_id", opts.chrooked_id);
    if (opts?.limit != null) params.set("limit", String(opts.limit));
    const query = params.toString();
    return getJson<{ entries: LedgerEntry[] }>(
      `/api/ledger${query ? `?${query}` : ""}`,
      signal,
    );
  },
} as const;
