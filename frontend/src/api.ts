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
  AbilityWrite,
  ApplyReportSummary,
  Behavior,
  BehaviorPacket,
  DexEntry,
  EngineKey,
  Move,
  MoveWrite,
  SpeciesOverride,
  Target,
  TypeChartCell,
  TypeChartEntry,
} from "./types";

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

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) {
    throw await toError(response);
  }
  return (await response.json()) as T;
}

async function sendJson<T>(
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

export const api = {
  // Reads
  dex: (signal?: AbortSignal) => getJson<DexEntry[]>("/api/dex", signal),
  moves: (signal?: AbortSignal) => getJson<Move[]>("/api/moves", signal),
  abilities: (signal?: AbortSignal) => getJson<Ability[]>("/api/abilities", signal),
  typeChart: (signal?: AbortSignal) =>
    getJson<TypeChartCell[]>("/api/type-chart", signal),
  behaviors: (signal?: AbortSignal) => getJson<Behavior[]>("/api/behaviors", signal),

  // Species (raw Override read + write)
  speciesOverride: (id: string, signal?: AbortSignal) =>
    getJson<SpeciesOverride>(`/api/species/${encodeURIComponent(id)}`, signal),
  putSpecies: (id: string, payload: SpeciesOverride) =>
    sendJson<SpeciesOverride>(
      "PUT",
      `/api/species/${encodeURIComponent(id)}`,
      payload,
    ),
  deleteSpecies: (id: string) =>
    sendJson<{ deleted: string }>("DELETE", `/api/species/${encodeURIComponent(id)}`),

  // Moves
  putMove: (id: string, payload: MoveWrite) =>
    sendJson<MoveWrite>("PUT", `/api/moves/${encodeURIComponent(id)}`, payload),
  deleteMove: (id: string, confirm?: boolean) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/moves/${encodeURIComponent(id)}${confirmQuery(confirm)}`,
    ),

  // Abilities
  putAbility: (id: string, payload: AbilityWrite) =>
    sendJson<AbilityWrite>("PUT", `/api/abilities/${encodeURIComponent(id)}`, payload),
  deleteAbility: (id: string, confirm?: boolean) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/abilities/${encodeURIComponent(id)}${confirmQuery(confirm)}`,
    ),

  // Type chart (one whole-list file → a write replaces the override set)
  putTypeChart: (entries: TypeChartEntry[]) =>
    sendJson<TypeChartEntry[]>("PUT", "/api/type-chart", entries),

  // Behaviors
  putBehavior: (id: string, payload: Behavior) =>
    sendJson<Behavior>("PUT", `/api/behaviors/${encodeURIComponent(id)}`, payload),
  deleteBehavior: (id: string) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/behaviors/${encodeURIComponent(id)}`,
    ),

  // Targets (M3 — register a fork, preview/apply the Ruleset, read its backdrop)
  targets: (signal?: AbortSignal) => getJson<Target[]>("/api/targets", signal),
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
  targetDex: (id: string) => (signal?: AbortSignal) =>
    getJson<DexEntry[]>(`/api/targets/${encodeURIComponent(id)}/dex`, signal),
  /** The target's abilities ⊕ Ruleset — the abilities backdrop for that fork. */
  targetAbilities: (id: string) => (signal?: AbortSignal) =>
    getJson<Ability[]>(
      `/api/targets/${encodeURIComponent(id)}/abilities`,
      signal,
    ),
  /** The target's moves ⊕ Ruleset — the moves backdrop for that fork. */
  targetMoves: (id: string) => (signal?: AbortSignal) =>
    getJson<Move[]>(`/api/targets/${encodeURIComponent(id)}/moves`, signal),
  /** The target's type chart ⊕ Ruleset — the type-chart backdrop for that fork. */
  targetTypeChart: (id: string) => (signal?: AbortSignal) =>
    getJson<TypeChartCell[]>(
      `/api/targets/${encodeURIComponent(id)}/type-chart`,
      signal,
    ),
  /** Fetch one behavior packet by its DATA-ONLY `packet_url`. */
  packet: (packetUrl: string, signal?: AbortSignal) =>
    getJson<BehaviorPacket>(packetUrl, signal),
} as const;
