/* Saved teams: a name → encoded-party map persisted in localStorage. Each value
   is exactly encodeParty()'s output — the same string the `team` URL param
   carries — so a saved team IS the share code; there's no separate team-code
   format to import/export (the Decision Ledger: the URL already covers sharing).

   Pure and Storage-agnostic: every function takes a StorageLike, so a test can
   pass a plain in-memory fake. Any corruption at the key — bad JSON, wrong
   shape, foreign data — reads back as an empty map, never a throw, so one
   poisoned key can't crash the Team tab. Unit-tested in savedTeams.test.ts. */

export const SAVED_TEAMS_KEY = "chrooked-saved-teams-v1";

/** The minimal slice of the Web Storage API this module needs. `localStorage`
    satisfies it; so does a small object in a test. */
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** name → encoded party (encodeParty output). */
export type SavedTeams = Record<string, string>;

/** A validated map is a plain object whose every value is a string. Anything
    else (array, null, nested objects, non-string values) is foreign data. */
function isSavedTeams(value: unknown): value is SavedTeams {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  return Object.values(value as Record<string, unknown>).every(
    (entry) => typeof entry === "string",
  );
}

/** Read the saved-teams map. Corrupt or foreign data collapses to `{}`. */
export function loadSavedTeams(storage: StorageLike): SavedTeams {
  const raw = storage.getItem(SAVED_TEAMS_KEY);
  if (!raw) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    return isSavedTeams(parsed) ? { ...parsed } : {};
  } catch {
    return {};
  }
}

/** Save (or overwrite) a team under a name, returning the new map. Blank names
    are rejected here too — the caller disables the control, but the store must
    never grow an empty key. */
export function saveTeam(
  storage: StorageLike,
  name: string,
  encoded: string,
): SavedTeams {
  const trimmed = name.trim();
  const current = loadSavedTeams(storage);
  if (trimmed === "") return current;
  const next: SavedTeams = { ...current, [trimmed]: encoded };
  storage.setItem(SAVED_TEAMS_KEY, JSON.stringify(next));
  return next;
}

/** Delete a team by name, returning the new map (a no-op if the name is absent). */
export function deleteTeam(storage: StorageLike, name: string): SavedTeams {
  const current = loadSavedTeams(storage);
  if (!(name in current)) return current;
  const next: SavedTeams = { ...current };
  delete next[name];
  storage.setItem(SAVED_TEAMS_KEY, JSON.stringify(next));
  return next;
}
