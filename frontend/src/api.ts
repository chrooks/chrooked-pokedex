/* The thin fetch layer over the local FastAPI surface. Read-only in M1.
   Errors carry the server's own message (the 503 "run snapshot" text, a 404,
   etc.) so the UI can surface it honestly instead of a generic failure. */

import type { Ability, Behavior, DexEntry, Move, TypeChartEntry } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) {
    const detail = await readDetail(response);
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Non-JSON error body; fall through to the status line.
  }
  return `Request failed (${response.status} ${response.statusText})`;
}

export const api = {
  dex: (signal?: AbortSignal) => getJson<DexEntry[]>("/api/dex", signal),
  moves: (signal?: AbortSignal) => getJson<Move[]>("/api/moves", signal),
  abilities: (signal?: AbortSignal) => getJson<Ability[]>("/api/abilities", signal),
  typeChart: (signal?: AbortSignal) => getJson<TypeChartEntry[]>("/api/type-chart", signal),
  behaviors: (signal?: AbortSignal) => getJson<Behavior[]>("/api/behaviors", signal),
} as const;
