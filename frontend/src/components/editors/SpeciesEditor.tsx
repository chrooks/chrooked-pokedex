/* The species editor — reached from the detail ledger's "Edit" button. It edits
   every Override kind: stats, types, abilities (scalar), plus the whole-list
   learnset and the evolution (added in slice 2b).

   The discipline that matters: the Ruleset stores *only* fields that differ from
   base. So the form starts from the merged values the user sees, but on save it
   emits an Override for a field ONLY where the value differs from base — editing
   Goodra's Speed writes `stats: { spe: 99 }`, never all six. The base 1.11.2
   snapshot carries no evolution, so any set evolution is always an Override. The
   raw Override is fetched first so its `aka` survives the round-trip. */

import { useEffect, useMemo, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faRotateLeft,
  faFloppyDisk,
} from "@fortawesome/free-solid-svg-icons";
import { api, ApiError } from "../../api";
import { STAT_ORDER, STAT_LABEL, TYPES, isEdited } from "../../lib/format";
import type {
  AbilitySlots,
  CanonicalMethod,
  DexEntry,
  Evolution,
  EvolvesInto,
  LearnsetMove,
  OverridableField,
  SpeciesOverride,
  TargetNamespace,
} from "../../types";
import { DexSprite } from "../DexSprite";
import { ScopeToggle } from "./ScopeToggle";
import { useSubmit } from "../../hooks/useSubmit";
import { rowId } from "../../lib/rowId";
import { canonicalize, collectInvalidFields } from "../../lib/entityValidation";
import { ComboField, NumberField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import {
  ADVANCED_ID,
  emptyMethodForm,
  requiredValueMissing,
  seedMethodForm,
  serializeMethod,
  type MethodForm,
} from "./evolutionMethod";
import "./editors.css";
import "../ledger/ledger-rows.css";

type Props = {
  entry: DexEntry;
  onDone: () => void;
  onSaved: () => void;
  /** Known ability names (base + Ruleset-owned) for the ability comboboxes. */
  abilityOptions: readonly string[];
  /** Known move names for the learnset comboboxes. */
  moveOptions: readonly string[];
  /** Known species names for the evo-from combobox. */
  speciesOptions: readonly string[];
  /** Canonical evolution methods for the Method dropdown + adaptive Value. */
  evolutionMethods: readonly CanonicalMethod[];
  /** Active backdrop target id — enables the base-vs-target scope toggle. */
  backdropTargetId?: string | null;
};

const ABILITY_SLOTS = ["primary", "secondary", "hidden"] as const;
type AbilitySlot = (typeof ABILITY_SLOTS)[number];

type StatForm = Record<string, number | "">;
type AbilityForm = Record<AbilitySlot, string>;
type LearnRow = { _id: number; level: number | ""; move: string };

export function SpeciesEditor({ entry, onDone, onSaved, abilityOptions, moveOptions, speciesOptions, evolutionMethods, backdropTargetId }: Props) {
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();

  // When editing on a Target's backdrop, the author can scope the edit to that
  // game's Override namespace instead of the base Ruleset. The namespace resolves
  // from the backdrop target; absent (unbound target or Canon dex) → base only.
  const [namespace, setNamespace] = useState<TargetNamespace | null>(null);
  const [scopeToTarget, setScopeToTarget] = useState(true);
  useEffect(() => {
    if (!backdropTargetId) {
      setNamespace(null);
      return;
    }
    const controller = new AbortController();
    api
      .targetNamespace(backdropTargetId, controller.signal)
      .then((ns) => !controller.signal.aborted && setNamespace(ns))
      .catch(() => !controller.signal.aborted && setNamespace(null));
    return () => controller.abort();
  }, [backdropTargetId]);
  // Default to scoping to the target whenever a namespace is available — the
  // author opened this game's backdrop on purpose. The effective scope string is
  // what the write routes to.
  const canScope = namespace !== null;
  const scope = canScope && scopeToTarget ? `target:${namespace.slug}` : "base";
  const targetFields = new Set<OverridableField>(entry.target_overridden_fields ?? []);

  // The raw Override carries `aka` we don't edit but must keep on save.
  const [raw, setRaw] = useState<SpeciesOverride | null>(null);
  const [rawLoaded, setRawLoaded] = useState(false);

  const [stats, setStats] = useState<StatForm>(() => initialStats(entry));
  const [type1, setType1] = useState(() => entry.types[0] ?? "");
  const [type2, setType2] = useState(() => entry.types[1] ?? "");
  const [abilities, setAbilities] = useState<AbilityForm>(() =>
    initialAbilities(entry.abilities),
  );
  const [learnset, setLearnset] = useState<LearnRow[]>(() =>
    entry.learnset.map((m) => ({ _id: rowId(), level: m.level, move: m.move })),
  );
  // The dex carries the pre-evo as a slug ("bulbasaur") for base evolutions and
  // the display name ("Bulbasaur") in from_name; an Override stores whatever was
  // authored (possibly stray-cased). Seed the display name and snap it to the
  // canonical species option so the field reads right and validates on load.
  const [evoFrom, setEvoFrom] = useState(() =>
    canonicalize(
      entry.evolution?.from_name ?? entry.evolution?.from ?? "",
      speciesOptions,
    ),
  );
  const [evoMethod, setEvoMethod] = useState<MethodForm>(() =>
    seedMethodForm(entry.evolution, evolutionMethods),
  );
  // Forward edges are the children's backward edges (base-derived). Each card is
  // an editable method form seeded from the edge's structured method_detail; on
  // Save we write each changed child's Override. The editor remounts per edit
  // session (the ledger toggles editing off on species change), so seeding in the
  // initializer is safe — evolutionMethods is loaded long before the modal opens.
  const seedForward = (edge: EvolvesInto): MethodForm =>
    seedMethodForm(
      { from: null, method: edge.method, method_detail: edge.method_detail },
      evolutionMethods,
    );
  const [forwardForms, setForwardForms] = useState<Record<string, MethodForm>>(() =>
    Object.fromEntries(entry.evolves_into.map((e) => [e.to, seedForward(e)])),
  );
  const forwardSeeds = useMemo(
    () => Object.fromEntries(entry.evolves_into.map((e) => [e.to, seedForward(e)])),
    // seedForward closes over entry + evolutionMethods; both are inputs to the
    // seed, so recompute when either changes (keeps the change-detection baseline
    // aligned with forwardForms, which is seeded from the same two).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [entry.chrooked_id, evolutionMethods],
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
      type1,
      type2,
      abilities,
      learnset,
      evoFrom,
      evoMethod,
      methods: evolutionMethods,
    });
    // Write this species, then fan out one write per CHANGED forward edge. A
    // forward edge lives on the child species, so we merge the new method into
    // the child's existing Override rather than replacing it (which would wipe
    // the child's stats/types/etc).
    const ok = await run(async () => {
      // Validate before any write so a half-filled method (e.g. "Trade w/ item"
      // with a blank item) never reaches the engine as a malformed token.
      if (evoFrom.trim() !== "" && requiredValueMissing(evoMethod, evolutionMethods)) {
        throw new Error("Set a value for the evolution method.");
      }
      const changedEdges = entry.evolves_into.filter(
        (edge) =>
          forwardForms[edge.to] &&
          JSON.stringify(forwardForms[edge.to]) !==
            JSON.stringify(forwardSeeds[edge.to]),
      );
      for (const edge of changedEdges) {
        if (requiredValueMissing(forwardForms[edge.to], evolutionMethods)) {
          throw new Error(`Set a value for ${edge.to_name}'s evolution method.`);
        }
      }
      await api.putSpecies(entry.chrooked_id, payload, scope);
      for (const edge of changedEdges) {
        await saveForwardEdge(edge, forwardForms[edge.to]);
      }
    });
    if (ok) {
      onSaved();
      onDone();
    }
  }

  async function saveForwardEdge(edge: EvolvesInto, form: MethodForm) {
    // Only a 404 means "no Override yet". Any other failure (network, 503) must
    // abort the save — treating it as null would replace the child's real
    // Override with a blank one carrying only the new evolution.
    const childRaw = await api.speciesOverride(edge.to).catch((caught: unknown) => {
      if (caught instanceof ApiError && caught.status === 404) return null;
      throw caught;
    });
    const method = serializeMethod(form, evolutionMethods);
    const payload: SpeciesOverride = {
      name: childRaw?.name ?? edge.to_name,
      chrooked_id: edge.to,
      aka: childRaw?.aka ?? (edge.to_dex !== null ? { dex: edge.to_dex } : {}),
      types: childRaw?.types ?? null,
      abilities: childRaw?.abilities ?? null,
      stats: childRaw?.stats ?? null,
      learnset: childRaw?.learnset ?? null,
      evolution: { from: entry.name, method },
    };
    await api.putSpecies(edge.to, payload, scope);
  }

  async function handleRevert() {
    const ok = await del.run(() => api.deleteSpecies(entry.chrooked_id, scope));
    if (ok) {
      onSaved();
      onDone();
    }
  }

  const invalidFields = useMemo(() => collectInvalidFields([
    ...ABILITY_SLOTS.map((slot) => ({
      id: `species-ability-${slot}`,
      value: abilities[slot],
      options: abilityOptions,
    })),
    ...learnset.map((row) => ({
      id: `learn-${row._id}-move`,
      value: row.move,
      options: moveOptions,
    })),
    { id: "species-evo-from", value: evoFrom, options: speciesOptions },
  ]), [abilities, learnset, evoFrom, abilityOptions, moveOptions, speciesOptions]);

  const busy = isSaving || del.isSaving || !rawLoaded;

  // Live BST: sum the six stat fields (a blank field counts as its base value,
  // matching the overrides-only save semantics), and the delta vs the base total.
  // Hidden when the base stat block is incomplete (some cosmetic forms carry none),
  // mirroring the read-only ledger's BST rule.
  const baseStatValues = STAT_ORDER.map((key) => baseStat(entry, key));
  const hasFullStats = baseStatValues.every((value) => value !== undefined);
  const baseBst = hasFullStats
    ? baseStatValues.reduce((sum, value) => sum + (value as number), 0)
    : undefined;
  const liveBst = hasFullStats
    ? STAT_ORDER.reduce((sum, key) => {
        const value = stats[key];
        return sum + (value === "" ? (baseStat(entry, key) as number) : value);
      }, 0)
    : undefined;
  const bstDelta =
    baseBst !== undefined && liveBst !== undefined ? liveBst - baseBst : 0;

  return (
    <form
      className="editor-form"
      aria-label={`Edit ${entry.name}`}
      onSubmit={(e) => {
        e.preventDefault();
        void handleSave();
      }}
    >
      {canScope && (
        <ScopeToggle
          targetLabel={namespace.label}
          scopeToTarget={scopeToTarget}
          onChange={setScopeToTarget}
        />
      )}

      <section className="editor-section" aria-labelledby="species-stats-heading">
        <h3 className="editor-section__heading" id="species-stats-heading">
          Base stats
          {targetFields.has("stats") && <TargetFieldBadge label={namespace?.label} />}
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
        {liveBst !== undefined && (
          <div className="editor-bst" id="species-bst" aria-live="polite">
            <span className="editor-bst__label">BST</span>
            <span className="editor-bst__total">{liveBst}</span>
            {bstDelta !== 0 ? (
              <span
                className="editor-bst__delta"
                data-dir={bstDelta > 0 ? "up" : "down"}
              >
                {bstDelta > 0 ? `+${bstDelta}` : bstDelta}
                <span className="editor-bst__base"> from {baseBst}</span>
              </span>
            ) : (
              <span className="editor-bst__unchanged">unchanged from base</span>
            )}
          </div>
        )}
      </section>

      <section className="editor-section" aria-labelledby="species-types-heading">
        <h3 className="editor-section__heading" id="species-types-heading">
          Types
          {targetFields.has("types") && <TargetFieldBadge label={namespace?.label} />}
        </h3>
        <div className="editor-form__grid">
          <ComboField
            id="species-type1"
            label="Type 1"
            options={TYPES}
            value={type1}
            changed={type1.trim() !== (baseTypes(entry)[0] ?? "")}
            onChange={setType1}
          />
          <ComboField
            id="species-type2"
            label="Type 2"
            hint="blank = single-type"
            options={TYPES}
            value={type2}
            changed={type2.trim() !== (baseTypes(entry)[1] ?? "")}
            onChange={setType2}
          />
        </div>
      </section>

      <section className="editor-section" aria-labelledby="species-abilities-heading">
        <h3 className="editor-section__heading" id="species-abilities-heading">
          Abilities
          {targetFields.has("abilities") && <TargetFieldBadge label={namespace?.label} />}
        </h3>
        <div className="editor-form__grid">
          {ABILITY_SLOTS.map((slot) => (
            <ComboField
              key={slot}
              id={`species-ability-${slot}`}
              label={slot}
              full={slot === "hidden"}
              options={abilityOptions}
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
          {targetFields.has("learnset") && <TargetFieldBadge label={namespace?.label} />}
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
                <ComboField
                  id={`learn-${row._id}-move`}
                  label="Move"
                  options={moveOptions}
                  value={row.move}
                  error={invalidFields.has(`learn-${row._id}-move`) ? "Unknown move" : null}
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
          {targetFields.has("evolution") && <TargetFieldBadge label={namespace?.label} />}
        </h3>
        <ComboField
          id="species-evo-from"
          label="Evolves from"
          hint="pre-evolution name; blank = no evolution Override"
          options={speciesOptions}
          full
          value={evoFrom}
          error={invalidFields.has("species-evo-from") ? "Unknown species" : null}
          onChange={setEvoFrom}
        />
        <div style={{ marginTop: "var(--space-2)" }}>
          <MethodEditor
            idPrefix="species-evo"
            form={evoMethod}
            onChange={setEvoMethod}
            methods={evolutionMethods}
            moveOptions={moveOptions}
          />
        </div>
        {/* Forward edges live on the children; editing a card and saving writes
            that child's Override (one PUT per changed card). */}
        {entry.evolves_into.length > 0 && (
          <EvolvesIntoEditor
            edges={entry.evolves_into}
            forms={forwardForms}
            onChange={(to, next) =>
              setForwardForms((prev) => ({ ...prev, [to]: next }))
            }
            methods={evolutionMethods}
            moveOptions={moveOptions}
            backdropTargetId={backdropTargetId}
          />
        )}
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
            <FontAwesomeIcon icon={faRotateLeft} aria-hidden="true" />
            Revert to base
          </button>
        )}
        <div className="editor-actions__commit">
          <button type="button" className="btn" disabled={busy} onClick={onDone}>
            Cancel
          </button>
          <button
            type="submit"
            id="editor-save-button"
            className="btn btn--primary"
            disabled={busy || invalidFields.size > 0}
          >
            <FontAwesomeIcon icon={faFloppyDisk} aria-hidden="true" />
            {isSaving
              ? "Saving…"
              : scope === "base"
                ? "Save to base"
                : `Save to ${namespace?.label ?? "target"}`}
          </button>
        </div>
      </div>
    </form>
  );
}

/** The Method dropdown + one adaptive Value field. The dropdown lists the
    canonical methods plus an "Advanced (raw token)" escape; the Value field's
    shape follows the selected method's value_kind (number / move picker / text /
    nothing). Reused by the backward edge and each forward-edge card. */
function MethodEditor({
  idPrefix,
  form,
  onChange,
  methods,
  moveOptions,
}: {
  idPrefix: string;
  form: MethodForm;
  onChange: (next: MethodForm) => void;
  methods: readonly CanonicalMethod[];
  moveOptions: readonly string[];
}) {
  const kind = methods.find((m) => m.id === form.id)?.value_kind ?? null;
  return (
    <div className="evo-method-row">
      <div className="field">
        <label className="field__label" htmlFor={`${idPrefix}-kind`}>
          Method
        </label>
        <select
          id={`${idPrefix}-kind`}
          className="field__select"
          value={form.id}
          onChange={(e) => onChange({ ...form, id: e.target.value, value: "" })}
        >
          {methods.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
          <option value={ADVANCED_ID}>Advanced (raw token)</option>
        </select>
      </div>
      {form.id === ADVANCED_ID ? (
        <>
          <div className="field">
            <label className="field__label" htmlFor={`${idPrefix}-engine`}>
              Engine
            </label>
            <select
              id={`${idPrefix}-engine`}
              className="field__select"
              value={form.rawEngine}
              onChange={(e) =>
                onChange({ ...form, rawEngine: e.target.value as MethodForm["rawEngine"] })
              }
            >
              <option value="pokeemerald">pokeemerald</option>
              <option value="essentials">essentials</option>
            </select>
          </div>
          <TextField
            id={`${idPrefix}-token`}
            label="Token"
            hint="e.g. EVO_LEVEL_FOG"
            value={form.rawToken}
            onChange={(v) => onChange({ ...form, rawToken: v })}
          />
          <TextField
            id={`${idPrefix}-param`}
            label="Param"
            value={form.rawParam}
            onChange={(v) => onChange({ ...form, rawParam: v })}
          />
        </>
      ) : (
        <MethodValueField
          idPrefix={idPrefix}
          kind={kind}
          form={form}
          onChange={onChange}
          moveOptions={moveOptions}
        />
      )}
    </div>
  );
}

/** The Value field for a canonical method, chosen by value_kind. `none` renders
    nothing; `move` gets the move picker; `item`/`map` stay free text until an
    item option source lands (#24). */
function MethodValueField({
  idPrefix,
  kind,
  form,
  onChange,
  moveOptions,
}: {
  idPrefix: string;
  kind: CanonicalMethod["value_kind"] | null;
  form: MethodForm;
  onChange: (next: MethodForm) => void;
  moveOptions: readonly string[];
}) {
  if (kind === null || kind === "none") return null;
  if (kind === "level") {
    return (
      <NumberField
        id={`${idPrefix}-value`}
        label="Level"
        min={1}
        max={100}
        value={form.value === "" ? "" : Number(form.value)}
        onChange={(v) => onChange({ ...form, value: v === "" ? "" : String(v) })}
      />
    );
  }
  if (kind === "move") {
    return (
      <ComboField
        id={`${idPrefix}-value`}
        label="Move"
        options={moveOptions}
        value={form.value}
        onChange={(v) => onChange({ ...form, value: v })}
      />
    );
  }
  // item or map — free text until item options exist (#24).
  return (
    <TextField
      id={`${idPrefix}-value`}
      label={kind === "item" ? "Item" : "Location"}
      hint={kind === "item" ? "internal name, e.g. FIRESTONE" : "map id"}
      value={form.value}
      onChange={(v) => onChange({ ...form, value: v })}
    />
  );
}

/** The editable "Evolves into" list: a sprite/name + a MethodEditor per forward
    branch. Each card edits the child species' backward method; the editor's Save
    writes the changed children. */
function EvolvesIntoEditor({
  edges,
  forms,
  onChange,
  methods,
  moveOptions,
  backdropTargetId,
}: {
  edges: EvolvesInto[];
  forms: Record<string, MethodForm>;
  onChange: (to: string, next: MethodForm) => void;
  methods: readonly CanonicalMethod[];
  moveOptions: readonly string[];
  backdropTargetId?: string | null;
}) {
  return (
    <div className="ledger__evo-group" style={{ marginTop: "var(--space-3)" }}>
      <span className="ledger__evo-dir">Evolves into</span>
      <ul className="ledger__evo-list">
        {edges.map((edge) => (
          <li key={edge.to} className="evo-into-card">
            <span className="ledger__evo-mon">
              <DexSprite
                chrookedId={edge.to}
                dex={edge.to_dex}
                name=""
                backdropTargetId={backdropTargetId}
                size={40}
              />
              <span className="ledger__evo-mon-name">{edge.to_name}</span>
            </span>
            <MethodEditor
              idPrefix={`evo-into-${edge.to}`}
              form={forms[edge.to] ?? emptyMethodForm()}
              onChange={(next) => onChange(edge.to, next)}
              methods={methods}
              moveOptions={moveOptions}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A small "this field is scoped to <Target> only" badge, shown beside a section
    heading when the active backdrop's Override namespace authored that field. */
function TargetFieldBadge({ label }: { label?: string }) {
  return (
    <span
      className="editor-target-badge"
      id={`field-target-badge-${(label ?? "target").toLowerCase()}`}
      title={`Scoped to ${label ?? "this target"} only`}
    >
      {label ?? "target"} only
    </span>
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
  // When the abilities field was overridden, `base.abilities` is the full base
  // snapshot — trust each slot EXACTLY, including a legit `null` ("no ability at
  // base"). The old `?? entry.abilities[slot]` collapsed a null base slot to the
  // MERGED (overridden) value, so buildOverride thought an override-only slot
  // matched base and dropped it on the next save — silently losing it (e.g.
  // editing Floatzel's types wiped its override-added secondary ability).
  // Only when abilities was never overridden does the merged value equal base.
  if (entry.base.abilities) return entry.base.abilities[slot];
  return entry.abilities[slot];
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

// --- parsing / comparison --------------------------------------------------- #

/** The non-blank type slots as an ordered list (1 or 2 entries). */
function currentTypes(type1: string, type2: string): string[] {
  return [type1, type2].map((t) => t.trim()).filter((t) => t.length > 0);
}

function sameStrings(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((value, i) => value === b[i]);
}

// --- the overrides-only payload builder ------------------------------------- #

type FormState = {
  stats: StatForm;
  type1: string;
  type2: string;
  abilities: AbilityForm;
  learnset: LearnRow[];
  evoFrom: string;
  evoMethod: MethodForm;
  methods: readonly CanonicalMethod[];
};

function buildOverride(
  entry: DexEntry,
  raw: SpeciesOverride | null,
  form: FormState,
): SpeciesOverride {
  // stats: same preserve-untouched discipline as abilities. If no stat input
  // changed from its seeded value, keep the raw Override's stats verbatim;
  // otherwise rebuild, emitting only stats that differ from base.
  const statsTouched = STAT_ORDER.some(
    (key) => String(form.stats[key]) !== String(entry.stats[key] ?? ""),
  );
  let statsField: Record<string, number> | null;
  if (!statsTouched) {
    statsField = raw?.stats ?? null;
  } else {
    const statOverride: Record<string, number> = {};
    for (const key of STAT_ORDER) {
      const value = form.stats[key];
      if (value !== "" && value !== baseStat(entry, key)) {
        statOverride[key] = value;
      }
    }
    statsField = Object.keys(statOverride).length > 0 ? statOverride : null;
  }

  // types: override only if the whole list differs from base
  const parsedTypes = currentTypes(form.type1, form.type2);
  const typesChanged = !sameStrings(parsedTypes, baseTypes(entry));

  // abilities: if the author didn't touch any slot (every input still equals the
  // value the form was seeded with), preserve the raw Override verbatim — editing
  // another field must never materialize base ability values into the Override
  // (the Seel bug: a learnset edit fattened {secondary} into all three slots).
  // Only when a slot actually changed do we rebuild, emitting slots that differ
  // from base.
  const abilitiesTouched = ABILITY_SLOTS.some(
    (slot) => form.abilities[slot].trim() !== (entry.abilities[slot] ?? "").trim(),
  );
  let abilitiesField: AbilitySlots | null;
  if (!abilitiesTouched) {
    abilitiesField = raw?.abilities ?? null;
  } else {
    const abilityOverride: Partial<AbilitySlots> = {};
    for (const slot of ABILITY_SLOTS) {
      const value = form.abilities[slot].trim();
      if (value !== "" && value !== (baseSlot(entry, slot) ?? "")) {
        abilityOverride[slot] = value;
      }
    }
    abilitiesField = Object.keys(abilityOverride).length
      ? {
          primary: abilityOverride.primary ?? null,
          secondary: abilityOverride.secondary ?? null,
          hidden: abilityOverride.hidden ?? null,
        }
      : null;
  }

  // learnset: a whole-list Override. Preserve-untouched first: if the edited list
  // still equals the seeded (merged) list, keep the raw Override verbatim so
  // editing another field never materializes the base learnset into the Override.
  // Otherwise emit a non-empty list that differs from base (an empty edit reverts
  // to base rather than writing an empty list).
  const editedLearnset: LearnsetMove[] = form.learnset
    .filter((r) => r.move.trim() !== "" && r.level !== "")
    .map((r) => ({ level: Number(r.level), move: r.move.trim() }));
  const seededLearnset = entry.learnset.map((m) => ({ level: m.level, move: m.move }));
  const learnsetTouched =
    JSON.stringify(editedLearnset) !== JSON.stringify(seededLearnset);
  let learnsetField: LearnsetMove[] | null;
  if (!learnsetTouched) {
    learnsetField = raw?.learnset ?? null;
  } else {
    learnsetField =
      editedLearnset.length > 0 &&
      JSON.stringify(editedLearnset) !== JSON.stringify(baseLearnset(entry))
        ? editedLearnset
        : null;
  }

  // evolution: the snapshot carries none, so any set evolution is an Override.
  // The method always serializes to a clean Override dict (never the backdrop
  // display string), via the discriminated-union form state.
  const evoFrom = form.evoFrom.trim();
  const method = serializeMethod(form.evoMethod, form.methods);
  const evolution: Evolution | null =
    evoFrom !== "" ? { from: evoFrom, method } : null;

  return {
    name: entry.name,
    chrooked_id: entry.chrooked_id,
    aka: raw?.aka ?? (entry.dex !== null ? { dex: entry.dex } : {}),
    types: typesChanged ? parsedTypes : null,
    abilities: abilitiesField,
    stats: statsField,
    learnset: learnsetField,
    evolution,
  };
}
