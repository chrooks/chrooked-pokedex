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
  Behavior,
  DexEntry,
  Move,
  SpeciesOverride,
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
  method: "PUT" | "DELETE",
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
    getJson<TypeChartEntry[]>("/api/type-chart", signal),
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
  putMove: (id: string, payload: Move) =>
    sendJson<Move>("PUT", `/api/moves/${encodeURIComponent(id)}`, payload),
  deleteMove: (id: string, confirm?: boolean) =>
    sendJson<{ deleted: string }>(
      "DELETE",
      `/api/moves/${encodeURIComponent(id)}${confirmQuery(confirm)}`,
    ),

  // Abilities
  putAbility: (id: string, payload: Ability) =>
    sendJson<Ability>("PUT", `/api/abilities/${encodeURIComponent(id)}`, payload),
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
} as const;
