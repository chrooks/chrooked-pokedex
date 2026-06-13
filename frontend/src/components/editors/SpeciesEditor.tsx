/* The species editor — reached from the detail ledger's "Edit" button. It edits
   every Override kind: stats, types, abilities (scalar), plus the whole-list
   learnset and the evolution (added in slice 2b).

   The discipline that matters: the Ruleset stores *only* fields that differ from
   base. So the form starts from the merged values the user sees, but on save it
   emits an Override for a field ONLY where the value differs from base — editing
   Goodra's Speed writes `stats: { spe: 99 }`, never all six. The base 1.11.2
   snapshot carries no evolution, so any set evolution is always an Override. The
   raw Override is fetched first so its `aka` survives the round-trip. */

import { useEffect, useState } from "react";
import { api } from "../../api";
import { STAT_ORDER, STAT_LABEL, isEdited } from "../../lib/format";
import type {
  AbilitySlots,
  DexEntry,
  Evolution,
  LearnsetMove,
  SpeciesOverride,
} from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { rowId } from "../../lib/rowId";
import { NumberField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import "./editors.css";

type Props = {
  entry: DexEntry;
  onDone: () => void;
  onSaved: () => void;
};

const ABILITY_SLOTS = ["primary", "secondary", "hidden"] as const;
type AbilitySlot = (typeof ABILITY_SLOTS)[number];

type StatForm = Record<string, number | "">;
type AbilityForm = Record<AbilitySlot, string>;
type LearnRow = { _id: number; level: number | ""; move: string };
type MethodRow = { _id: number; key: string; value: string };

export function SpeciesEditor({ entry, onDone, onSaved }: Props) {
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();

  // The raw Override carries `aka` we don't edit but must keep on save.
  const [raw, setRaw] = useState<SpeciesOverride | null>(null);
  const [rawLoaded, setRawLoaded] = useState(false);

  const [stats, setStats] = useState<StatForm>(() => initialStats(entry));
  const [types, setTypes] = useState(() => entry.types.join(", "));
  const [abilities, setAbilities] = useState<AbilityForm>(() =>
    initialAbilities(entry.abilities),
  );
  const [learnset, setLearnset] = useState<LearnRow[]>(() =>
    entry.learnset.map((m) => ({ _id: rowId(), level: m.level, move: m.move })),
  );
  const [evoFrom, setEvoFrom] = useState(() => entry.evolution?.from ?? "");
  const [evoMethod, setEvoMethod] = useState<MethodRow[]>(() =>
    initialMethod(entry.evolution),
  );

  useEffect(() => {
    const controller = new AbortController();
    // Reset on species change so a stale "loaded" never lets a save fire before
    // this species' raw Override is in hand.
    setRaw(null);
    setRawLoaded(false);
    api
      .speciesOverride(entry.chrooked_id, controller.signal)
      .then((override) => !controller.signal.aborted && setRaw(override))
      .catch(() => {
        // 404 = no Override yet (an untouched species being edited for the
        // first time). Any other error just means no passthrough data to keep.
      })
      .finally(() => !controller.signal.aborted && setRawLoaded(true));
    return () => controller.abort();
  }, [entry.chrooked_id]);

  async function handleSave() {
    const payload = buildOverride(entry, raw, {
      stats,
      types,
      abilities,
      learnset,
      evoFrom,
      evoMethod,
    });
    const ok = await run(() => api.putSpecies(entry.chrooked_id, payload));
    if (ok) {
      onSaved();
      onDone();
    }
  }

  async function handleRevert() {
    const ok = await del.run(() => api.deleteSpecies(entry.chrooked_id));
    if (ok) {
      onSaved();
      onDone();
    }
  }

  const busy = isSaving || del.isSaving || !rawLoaded;

  return (
    <form
      className="editor-form"
      aria-label={`Edit ${entry.name}`}
      onSubmit={(e) => {
        e.preventDefault();
        void handleSave();
      }}
    >
      <section className="editor-section" aria-labelledby="species-stats-heading">
        <h3 className="editor-section__heading" id="species-stats-heading">
          Base stats
        </h3>
        <div className="editor-form__grid editor-form__grid--stats">
          {STAT_ORDER.map((key) => (
            <NumberField
              key={key}
              id={`species-stat-${key}`}
              label={STAT_LABEL[key]}
              min={0}
              max={255}
              value={stats[key]}
              changed={stats[key] !== "" && stats[key] !== baseStat(entry, key)}
              onChange={(value) => setStats((s) => ({ ...s, [key]: value }))}
            />
          ))}
        </div>
      </section>

      <section className="editor-section" aria-labelledby="species-types-heading">
        <h3 className="editor-section__heading" id="species-types-heading">
          Types
        </h3>
        <TextField
          id="species-types"
          label="Types"
          hint="comma-separated, e.g. Water, Dragon"
          full
          value={types}
          changed={!sameStrings(parseTypes(types), baseTypes(entry))}
          onChange={setTypes}
        />
      </section>

      <section className="editor-section" aria-labelledby="species-abilities-heading">
        <h3 className="editor-section__heading" id="species-abilities-heading">
          Abilities
        </h3>
        <div className="editor-form__grid">
          {ABILITY_SLOTS.map((slot) => (
            <TextField
              key={slot}
              id={`species-ability-${slot}`}
              label={slot}
              full={slot === "hidden"}
              value={abilities[slot]}
              changed={
                abilities[slot].trim() !== "" &&
                abilities[slot].trim() !== (baseSlot(entry, slot) ?? "")
              }
              onChange={(value) => setAbilities((a) => ({ ...a, [slot]: value }))}
            />
          ))}
        </div>
      </section>

      <section className="editor-section" aria-labelledby="species-learnset-heading">
        <h3 className="editor-section__heading" id="species-learnset-heading">
          Learnset
        </h3>
        <div className="row-list">
          {learnset.length === 0 && (
            <p className="row-list__empty">No learnset Override (uses base).</p>
          )}
          {learnset.map((row, i) => (
            <div key={row._id} className="row-list__row row-list__row--inline">
              <div className="tc-row">
                <NumberField
                  id={`learn-${row._id}-level`}
                  label="Lv"
                  min={0}
                  max={100}
                  value={row.level}
                  onChange={(v) =>
                    setLearnset((ls) =>
                      ls.map((r, j) => (j === i ? { ...r, level: v } : r)),
                    )
                  }
                />
                <span className="tc-row__vs" aria-hidden="true">
                  ·
                </span>
                <TextField
                  id={`learn-${row._id}-move`}
                  label="Move"
                  value={row.move}
                  onChange={(v) =>
                    setLearnset((ls) =>
                      ls.map((r, j) => (j === i ? { ...r, move: v } : r)),
                    )
                  }
                />
                <button
                  type="button"
                  className="row-list__remove"
                  aria-label={`Remove learnset row ${i + 1}`}
                  onClick={() => setLearnset((ls) => ls.filter((_, j) => j !== i))}
                >
                  ×
                </button>
              </div>
            </div>
          ))}
          <button
            type="button"
            className="row-list__add"
            aria-label="Add learnset move"
            onClick={() =>
              setLearnset((ls) => [...ls, { _id: rowId(), level: 1, move: "" }])
            }
          >
            + Add move
          </button>
        </div>
      </section>

      <section className="editor-section" aria-labelledby="species-evolution-heading">
        <h3 className="editor-section__heading" id="species-evolution-heading">
          Evolution
        </h3>
        <TextField
          id="species-evo-from"
          label="Evolves from"
          hint="pre-evolution name; blank = no evolution Override"
          full
          value={evoFrom}
          onChange={setEvoFrom}
        />
        <div className="row-list" style={{ marginTop: "var(--space-2)" }}>
          {evoMethod.map((row, i) => (
            <div key={row._id} className="row-list__row row-list__row--inline">
              <div className="tc-row">
                <TextField
                  id={`evo-${row._id}-key`}
                  label="Method key"
                  hint="e.g. level"
                  value={row.key}
                  onChange={(v) =>
                    setEvoMethod((m) =>
                      m.map((r, j) => (j === i ? { ...r, key: v } : r)),
                    )
                  }
                />
                <span className="tc-row__vs" aria-hidden="true">
                  =
                </span>
                <TextField
                  id={`evo-${row._id}-value`}
                  label="Value"
                  value={row.value}
                  onChange={(v) =>
                    setEvoMethod((m) =>
                      m.map((r, j) => (j === i ? { ...r, value: v } : r)),
                    )
                  }
                />
                <button
                  type="button"
                  className="row-list__remove"
                  aria-label={`Remove evolution method ${i + 1}`}
                  onClick={() => setEvoMethod((m) => m.filter((_, j) => j !== i))}
                >
                  ×
                </button>
              </div>
            </div>
          ))}
          <button
            type="button"
            className="row-list__add"
            aria-label="Add evolution method condition"
            onClick={() =>
              setEvoMethod((m) => [...m, { _id: rowId(), key: "", value: "" }])
            }
          >
            + Add method condition
          </button>
        </div>
      </section>

      {(error !== null || del.error !== null) && (
        <FormError
          key={`${error ?? ""}|${del.error ?? ""}|${(del.citing ?? []).join(",")}`}
          message={error ?? del.error ?? ""}
          citing={del.citing}
        />
      )}

      <div className="editor-actions">
        {isEdited(entry) && rawLoaded && (
          <button
            type="button"
            className="btn btn--danger"
            aria-label={`Revert ${entry.name} to base`}
            disabled={busy}
            onClick={() => void handleRevert()}
          >
            Revert to base
          </button>
        )}
        <span className="editor-actions__spacer" />
        <button type="button" className="btn" disabled={busy} onClick={onDone}>
          Cancel
        </button>
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {isSaving ? "Saving…" : "Save Override"}
        </button>
      </div>
    </form>
  );
}

// --- base lookups (base payload holds pre-override values for changed fields;
//     an unchanged field's base value just is its merged value) --------------- #

function baseStat(entry: DexEntry, key: string): number | undefined {
  return entry.base.stats?.[key] ?? entry.stats[key];
}

function baseTypes(entry: DexEntry): string[] {
  return entry.base.types ?? entry.types;
}

function baseSlot(entry: DexEntry, slot: AbilitySlot): string | null {
  return entry.base.abilities?.[slot] ?? entry.abilities[slot];
}

function baseLearnset(entry: DexEntry): LearnsetMove[] {
  return entry.base.learnset ?? entry.learnset;
}

// --- form initial state ----------------------------------------------------- #

function initialStats(entry: DexEntry): StatForm {
  const form: StatForm = {};
  for (const key of STAT_ORDER) {
    form[key] = entry.stats[key] ?? "";
  }
  return form;
}

function initialAbilities(slots: AbilitySlots): AbilityForm {
  return {
    primary: slots.primary ?? "",
    secondary: slots.secondary ?? "",
    hidden: slots.hidden ?? "",
  };
}

function initialMethod(evolution: Evolution | null): MethodRow[] {
  if (evolution === null) return [];
  return Object.entries(evolution.method).map(([key, value]) => ({
    _id: rowId(),
    key,
    value: String(value),
  }));
}

// --- parsing / comparison --------------------------------------------------- #

function parseTypes(text: string): string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

function sameStrings(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((value, i) => value === b[i]);
}

function parseMethodValue(value: string): number | string {
  const trimmed = value.trim();
  return /^-?\d+$/.test(trimmed) ? Number(trimmed) : trimmed;
}

// --- the overrides-only payload builder ------------------------------------- #

type FormState = {
  stats: StatForm;
  types: string;
  abilities: AbilityForm;
  learnset: LearnRow[];
  evoFrom: string;
  evoMethod: MethodRow[];
};

function buildOverride(
  entry: DexEntry,
  raw: SpeciesOverride | null,
  form: FormState,
): SpeciesOverride {
  // stats: only those differing from base
  const statOverride: Record<string, number> = {};
  for (const key of STAT_ORDER) {
    const value = form.stats[key];
    if (value !== "" && value !== baseStat(entry, key)) {
      statOverride[key] = value;
    }
  }

  // types: override only if the whole list differs from base
  const parsedTypes = parseTypes(form.types);
  const typesChanged = !sameStrings(parsedTypes, baseTypes(entry));

  // abilities: only slots that differ from base (a cleared slot is left as-is)
  const abilityOverride: Partial<AbilitySlots> = {};
  for (const slot of ABILITY_SLOTS) {
    const value = form.abilities[slot].trim();
    if (value !== "" && value !== (baseSlot(entry, slot) ?? "")) {
      abilityOverride[slot] = value;
    }
  }
  const hasAbilityOverride = Object.keys(abilityOverride).length > 0;

  // learnset: a whole-list Override. Emit only a non-empty list that differs
  // from base; an empty edit reverts to base rather than writing an empty list.
  const editedLearnset: LearnsetMove[] = form.learnset
    .filter((r) => r.move.trim() !== "" && r.level !== "")
    .map((r) => ({ level: Number(r.level), move: r.move.trim() }));
  const learnsetChanged =
    editedLearnset.length > 0 &&
    JSON.stringify(editedLearnset) !== JSON.stringify(baseLearnset(entry));

  // evolution: the snapshot carries none, so any set evolution is an Override.
  const evoFrom = form.evoFrom.trim();
  const method: Record<string, number | string> = {};
  for (const row of form.evoMethod) {
    const key = row.key.trim();
    if (key !== "") method[key] = parseMethodValue(row.value);
  }
  const evolution: Evolution | null =
    evoFrom !== "" ? { from: evoFrom, method } : null;

  return {
    name: entry.name,
    chrooked_id: entry.chrooked_id,
    aka: raw?.aka ?? (entry.dex !== null ? { dex: entry.dex } : {}),
    types: typesChanged ? parsedTypes : null,
    abilities: hasAbilityOverride
      ? {
          primary: abilityOverride.primary ?? null,
          secondary: abilityOverride.secondary ?? null,
          hidden: abilityOverride.hidden ?? null,
        }
      : null,
    stats: Object.keys(statOverride).length > 0 ? statOverride : null,
    learnset: learnsetChanged ? editedLearnset : null,
    evolution,
  };
}
