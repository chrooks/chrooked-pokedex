/* The species editor — reached from the detail ledger's "Edit" button. It edits
   the three scalar Override kinds (stats, types, abilities); learnset and
   evolution editing land in slice 2b and ride along untouched here.

   The discipline that matters: the Ruleset stores *only* fields that differ from
   base. So the form starts from the merged values the user sees, but on save it
   emits an Override for a field ONLY where the value differs from base — editing
   Goodra's Speed writes `stats: { spe: 99 }`, never all six. The raw Override is
   fetched first so its learnset/evolution/aka survive the round-trip. */

import { useEffect, useState } from "react";
import { api } from "../../api";
import { STAT_ORDER, STAT_LABEL } from "../../lib/format";
import type { AbilitySlots, DexEntry, SpeciesOverride } from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { NumberField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import { isEdited } from "../../lib/format";
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

export function SpeciesEditor({ entry, onDone, onSaved }: Props) {
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();

  // The raw Override carries learnset/evolution/aka we don't edit but must keep.
  const [raw, setRaw] = useState<SpeciesOverride | null>(null);
  const [rawLoaded, setRawLoaded] = useState(false);

  const [stats, setStats] = useState<StatForm>(() => initialStats(entry));
  const [types, setTypes] = useState(() => entry.types.join(", "));
  const [abilities, setAbilities] = useState<AbilityForm>(() =>
    initialAbilities(entry.abilities),
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
    const payload = buildOverride(entry, raw, stats, types, abilities);
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
      onSubmit={(e) => {
        e.preventDefault();
        void handleSave();
      }}
    >
      <section className="editor-section">
        <h3 className="editor-section__heading">Base stats</h3>
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

      <section className="editor-section">
        <h3 className="editor-section__heading">Types</h3>
        <TextField
          id="species-types"
          label="Types"
          hint="comma-separated, e.g. Water, Dragon"
          full
          value={types}
          changed={!sameTypes(parseTypes(types), baseTypes(entry))}
          onChange={setTypes}
        />
      </section>

      <section className="editor-section">
        <h3 className="editor-section__heading">Abilities</h3>
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

// --- parsing / comparison --------------------------------------------------- #

function parseTypes(text: string): string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

function sameTypes(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((value, i) => value === b[i]);
}

// --- the overrides-only payload builder ------------------------------------- #

function buildOverride(
  entry: DexEntry,
  raw: SpeciesOverride | null,
  stats: StatForm,
  typesText: string,
  abilities: AbilityForm,
): SpeciesOverride {
  // stats: only those differing from base
  const statOverride: Record<string, number> = {};
  for (const key of STAT_ORDER) {
    const value = stats[key];
    if (value !== "" && value !== baseStat(entry, key)) {
      statOverride[key] = value;
    }
  }

  // types: override only if the whole list differs from base
  const parsedTypes = parseTypes(typesText);
  const typesChanged = !sameTypes(parsedTypes, baseTypes(entry));

  // abilities: only slots that differ from base (a cleared slot is left as-is
  // in 2a — removing a base ability is a 2b concern)
  const abilityOverride: Partial<AbilitySlots> = {};
  for (const slot of ABILITY_SLOTS) {
    const value = abilities[slot].trim();
    if (value !== "" && value !== (baseSlot(entry, slot) ?? "")) {
      abilityOverride[slot] = value;
    }
  }
  const hasAbilityOverride = Object.keys(abilityOverride).length > 0;

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
    learnset: raw?.learnset ?? null,
    evolution: raw?.evolution ?? null,
  };
}
