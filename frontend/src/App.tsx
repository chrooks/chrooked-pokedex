import { useEffect, useState } from "react";

interface DexEntry {
  dex: number | null;
  chrooked_id: string;
  name: string;
  types: string[];
  overridden_fields: string[];
}

type Health = "checking" | "ok" | "down";

/**
 * Milestone 0 placeholder shell. It proves the API wiring end to end — the
 * health probe and the live Canon dex count — and is replaced by the real
 * sprite grid in Milestone 1.
 */
export default function App() {
  const [health, setHealth] = useState<Health>("checking");
  const [entries, setEntries] = useState<DexEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? setHealth("ok") : setHealth("down")))
      .catch(() => setHealth("down"));

    fetch("/api/dex")
      .then((r) => {
        if (!r.ok) throw new Error(`dex request failed (${r.status})`);
        return r.json();
      })
      .then((data: DexEntry[]) => setEntries(data))
      .catch((e: Error) => setError(e.message));
  }, []);

  const editedCount = entries?.filter((e) => e.overridden_fields.length > 0).length;

  return (
    <main id="app-shell" style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1 id="app-title">chrooked-pokedex</h1>
      <p id="api-health">
        API: <strong>{health}</strong>
      </p>
      {error && (
        <p id="dex-error" role="alert" style={{ color: "crimson" }}>
          {error}
        </p>
      )}
      {entries && (
        <p id="dex-summary">
          Canon dex: <strong>{entries.length}</strong> species
          {editedCount !== undefined && (
            <>
              {" "}
              · <strong>{editedCount}</strong> edited by the Ruleset
            </>
          )}
        </p>
      )}
    </main>
  );
}
