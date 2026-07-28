import { beforeEach, describe, expect, it } from "vitest";
import {
  deleteTeam,
  loadSavedTeams,
  saveTeam,
  SAVED_TEAMS_KEY,
  type StorageLike,
} from "./savedTeams";

/** A hermetic in-memory Storage-like fake — no jsdom localStorage needed. */
function fakeStorage(seed?: string): StorageLike & { raw(): string | null } {
  const store = new Map<string, string>();
  if (seed !== undefined) store.set(SAVED_TEAMS_KEY, seed);
  return {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => {
      store.set(key, value);
    },
    raw: () => store.get(SAVED_TEAMS_KEY) ?? null,
  };
}

describe("savedTeams", () => {
  let storage: ReturnType<typeof fakeStorage>;

  beforeEach(() => {
    storage = fakeStorage();
  });

  it("returns an empty map when nothing is stored", () => {
    expect(loadSavedTeams(storage)).toEqual({});
  });

  it("saves a team and reads it back", () => {
    const next = saveTeam(storage, "Rain", "politoed,kingdra");
    expect(next).toEqual({ Rain: "politoed,kingdra" });
    expect(loadSavedTeams(storage)).toEqual({ Rain: "politoed,kingdra" });
  });

  it("trims the name and overwrites an existing team of the same name", () => {
    saveTeam(storage, "Rain", "politoed");
    const next = saveTeam(storage, "  Rain  ", "politoed,kingdra~Swift Swim");
    expect(next).toEqual({ Rain: "politoed,kingdra~Swift Swim" });
  });

  it("refuses to store a blank name", () => {
    const next = saveTeam(storage, "   ", "gengar");
    expect(next).toEqual({});
    expect(storage.raw()).toBeNull();
  });

  it("deletes a team by name and leaves the rest", () => {
    saveTeam(storage, "Rain", "politoed");
    saveTeam(storage, "Sun", "ninetales");
    const next = deleteTeam(storage, "Rain");
    expect(next).toEqual({ Sun: "ninetales" });
    expect(loadSavedTeams(storage)).toEqual({ Sun: "ninetales" });
  });

  it("delete of a missing name is a no-op", () => {
    saveTeam(storage, "Sun", "ninetales");
    expect(deleteTeam(storage, "Nope")).toEqual({ Sun: "ninetales" });
  });

  it("reads corrupt JSON as an empty map", () => {
    expect(loadSavedTeams(fakeStorage("{not json"))).toEqual({});
  });

  it("reads foreign-shaped data (array) as an empty map", () => {
    expect(loadSavedTeams(fakeStorage('["a","b"]'))).toEqual({});
  });

  it("reads a map with non-string values as an empty map", () => {
    expect(loadSavedTeams(fakeStorage('{"Rain":42}'))).toEqual({});
  });

  it("does not mutate the stored object it returns", () => {
    saveTeam(storage, "Rain", "politoed");
    const loaded = loadSavedTeams(storage);
    loaded.Rain = "tampered";
    expect(loadSavedTeams(storage)).toEqual({ Rain: "politoed" });
  });
});
