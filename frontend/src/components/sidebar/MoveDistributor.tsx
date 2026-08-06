/* The move Distribution tab's rule/prompt-driven seeder (issue: move-distribute).

   Top: a seeder — pick a preset rule (types + attack split + level window) OR
   type a freeform prompt (mechanical or thematic). Running it calls
   `POST /api/moves/{id}/distribute` (deterministic for rule, LLM for prompt) and
   shows a pokeball spinner while it computes.

   Bottom: the proposed recipients as selectable rows grouped by evolution line —
   sprite + name + a gap-placed level you can edit, a checkbox (all selected by
   default), a per-line "evo line" toggle, and remove. Apply writes the move into
   each selected species' learnset (append-only) via the existing per-species PUT,
   reusing the distributionEdits merge so untouched Override fields survive.

   Editing is disabled in backdrop / read-only mode (a fork preview never writes
   to the base Ruleset). */

import { useMemo, useState } from "react";
import { api, ApiError } from "../../api";
import { TYPES } from "../../lib/format";
import type {
  DistributeRequest,
  DistributeRow,
  DistributeSplit,
  DistributePreset,
  DistributeRarity,
} from "../../types";
import { DexSprite } from "../DexSprite";
import { PokeballSpinner } from "../PokeballSpinner";
import { TypeChip } from "../TypeChip";
import { CategoryGlyph, type Category } from "../CategoryChip";
import { FormError } from "../editors/FormFeedback";
import "../editors/editors.css";
import "../proposal/proposal.css";
import "./move-distributor.css";

type Props = {
  /** The move being distributed (its chrooked_id + display name). */
  move: { chrooked_id: string; name: string };
  /** Backdrop / read-only mode disables every write affordance. */
  readOnly: boolean;
  backdropTargetId?: string | null;
  /** Called after a successful Apply so the parent reloads its data. */
  onSaved: () => void;
};

/* The split buttons carry the same glyph the moves table and the move editor use.
   `strong-*` is the same physical/special axis read loosely (a lean, not a hard
   split), so it wears the same shape rather than a second private vocabulary;
   `any` has no side, so it shows no glyph. */
const SPLITS: { value: DistributeSplit; label: string; category: Category | null }[] = [
  { value: "physical", label: "Physical", category: "physical" },
  { value: "special", label: "Special", category: "special" },
  { value: "strong-physical", label: "Phys-lean", category: "physical" },
  { value: "strong-special", label: "Spec-lean", category: "special" },
  { value: "any", label: "Any", category: null },
];

const RARITIES: { value: DistributeRarity; label: string; hint: string }[] = [
  { value: "common", label: "Common", hint: "everyone plausible" },
  { value: "uncommon", label: "Uncommon", hint: "skip the weakest fits" },
  { value: "rare", label: "Rare", hint: "only strong/notable users" },
  { value: "signature", label: "Signature", hint: "the few iconic users" },
];

const PRESETS: DistributePreset[] = ["start", "early", "mid", "late", "end"];
const PRESET_RANGES: Record<DistributePreset, [number, number]> = {
  start: [1, 5],
  early: [6, 15],
  mid: [16, 35],
  late: [36, 48],
  end: [48, 64],
};

export function MoveDistributor({
  move,
  readOnly,
  backdropTargetId,
  onSaved,
}: Props) {
  // Collapsed by default: the tab leads with the editable list, and the bulk
  // seeder only unfolds when the author reaches for ✦ suggest.
  const [open, setOpen] = useState(false);
  const [types, setTypes] = useState<Set<string>>(new Set());
  const [split, setSplit] = useState<DistributeSplit>("physical");
  const [windowMode, setWindowMode] = useState<DistributePreset | "custom">("early");
  const [lo, setLo] = useState(6);
  const [hi, setHi] = useState(15);
  const [prompt, setPrompt] = useState("");
  const [rarity, setRarity] = useState<DistributeRarity>("common");
  const [includeEvolutions, setIncludeEvolutions] = useState(true);

  const [phase, setPhase] = useState<"idle" | "running" | "applying">("idle");
  const [rows, setRows] = useState<DistributeRow[]>([]);
  const [rationale, setRationale] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [appliedNote, setAppliedNote] = useState<string | null>(null);

  // Per-row selection + editable level, keyed by chrooked_id.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [levels, setLevels] = useState<Map<string, number>>(new Map());

  // Rows grouped by evolution line, preserving the server's stable order.
  const groups = useMemo(() => {
    const order: string[] = [];
    const byLine = new Map<string, DistributeRow[]>();
    for (const row of rows) {
      if (!byLine.has(row.line_id)) {
        byLine.set(row.line_id, []);
        order.push(row.line_id);
      }
      byLine.get(row.line_id)!.push(row);
    }
    return order.map((lineId) => ({ lineId, rows: byLine.get(lineId)! }));
  }, [rows]);

  const selectableCount = rows.filter((r) => !r.already_has).length;
  const selectedCount = rows.filter(
    (r) => selected.has(r.chrooked_id) && !r.already_has,
  ).length;

  function toggleType(type: string) {
    setTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  function currentWindow(): Pick<DistributeRequest, "levels" | "preset"> {
    if (windowMode === "custom") return { levels: [lo, hi] };
    return { preset: windowMode };
  }

  // One unified seeder: a type rule and/or a prompt. At least one is required;
  // a type makes the rule meaningful, split refines it, and the prompt adds a
  // semantic requirement on top (e.g. "has feet/legs").
  const canRun =
    phase === "idle" && (types.size > 0 || prompt.trim().length > 0);

  async function handleDistribute() {
    setPhase("running");
    setError(null);
    setAppliedNote(null);
    const body: DistributeRequest = {
      ...currentWindow(),
      include_evolutions: includeEvolutions,
      rarity,
    };
    if (types.size > 0) body.rule = { types: [...types], split };
    if (prompt.trim().length > 0) body.prompt = prompt.trim();
    try {
      const result = await api.distributeMove(move.chrooked_id, body);
      setRows(result.rows);
      setRationale(result.rationale);
      setWarnings(result.warnings);
      // All selected by default, except species that already learn the move.
      setSelected(
        new Set(result.rows.filter((r) => !r.already_has).map((r) => r.chrooked_id)),
      );
      setLevels(new Map(result.rows.map((r) => [r.chrooked_id, r.level])));
    } catch (caught: unknown) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : caught instanceof Error
            ? caught.message
            : "Unexpected error";
      setError(message);
      setRows([]);
    } finally {
      setPhase((p) => (p === "running" ? "idle" : p));
    }
  }

  function toggleRow(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleLineRelatives(lineRows: DistributeRow[], on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const row of lineRows) {
        if (row.matched || row.already_has) continue; // anchors + owned stay as-is
        if (on) next.add(row.chrooked_id);
        else next.delete(row.chrooked_id);
      }
      return next;
    });
  }

  function setLevel(id: string, value: number) {
    setLevels((prev) => new Map(prev).set(id, value));
  }

  async function handleApply() {
    setPhase("applying");
    setError(null);
    const targets = rows.filter(
      (r) => selected.has(r.chrooked_id) && !r.already_has,
    );
    try {
      // One request writes the whole distribution append-only (server-side),
      // then emits a single data-change — no per-species GET+PUT fan-out.
      const result = await api.applyDistribution(
        move.chrooked_id,
        targets.map((r) => ({
          chrooked_id: r.chrooked_id,
          level: levels.get(r.chrooked_id) ?? r.level,
        })),
      );
      setPhase("idle");
      if (result.failed.length > 0) {
        setWarnings(
          result.failed.map((f) => `${f.chrooked_id}: ${f.error}`),
        );
      }
      setAppliedNote(`Added ${move.name} to ${result.count} species.`);
      setRows([]);
      setSelected(new Set());
      setOpen(false);
      onSaved();
    } catch (caught: unknown) {
      setPhase("idle");
      setError(caught instanceof Error ? caught.message : "Unexpected error");
    }
  }

  // Read-only (backdrop): the editable list below handles the read view; the
  // bulk seeder simply isn't offered.
  if (readOnly) return null;

  return (
    <section
      id="move-distributor"
      className="proposal proposal--section"
      data-phase={phase}
    >
      <div className="proposal__head">
        <h3 className="ledger__heading proposal__heading">Bulk distribute</h3>
        {!open && (
          <button
            type="button"
            id="move-distribute-suggest"
            className="proposal__suggest"
            onClick={() => setOpen(true)}
            aria-label="Suggest a bulk distribution by rule or prompt"
          >
            <span aria-hidden="true">✦</span> suggest
          </button>
        )}
        {phase === "running" && (
          <PokeballSpinner id="move-distribute-spinner" size={20} label="Distributing…" />
        )}
        {open && phase !== "running" && (
          <button
            type="button"
            id="move-distribute-close"
            className="proposal__dismiss"
            onClick={() => {
              setOpen(false);
              setRows([]);
              setError(null);
            }}
          >
            Close
          </button>
        )}
      </div>

      {appliedNote !== null && (
        <p className="dseed__applied" id="dist-applied" aria-live="polite">
          {appliedNote}
        </p>
      )}

      {open && (
      <>
      {/* --- Seeder: one unified form — a type rule and/or a prompt --------- */}
      <div className="dseed" id="dseed">
        <p className="dseed__hint" id="dseed-hint">
          Pick a type (with an optional attack split) and/or write a prompt. The
          prompt adds a requirement on top of the rule.
        </p>

        <div className="dseed__field">
          <span className="dseed__label">Types</span>
          <div className="dseed__types" id="dseed-types">
            {TYPES.map((type) => (
              <button
                key={type}
                type="button"
                id={`dseed-type-${type.toLowerCase()}`}
                className="dseed__type"
                data-on={types.has(type) || undefined}
                aria-pressed={types.has(type)}
                onClick={() => toggleType(type)}
              >
                <TypeChip type={type} variant="full" />
              </button>
            ))}
          </div>
        </div>

        <div className="dseed__field">
          <span className="dseed__label">Attack split</span>
          <div className="dseed__segmented" id="dseed-split">
            {SPLITS.map((s) => (
              <button
                key={s.value}
                type="button"
                id={`dseed-split-${s.value}`}
                className="dseed__seg"
                data-category={s.category ?? undefined}
                data-on={split === s.value || undefined}
                onClick={() => setSplit(s.value)}
              >
                {s.category && <CategoryGlyph category={s.category} />}
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="dseed__field">
          <label className="dseed__label" htmlFor="dseed-prompt">
            Prompt <span className="dseed__optional">(optional)</span>
          </label>
          <textarea
            id="dseed-prompt"
            className="field__textarea"
            rows={3}
            placeholder="e.g. requires Pokémon who have feet or legs — or — could plausibly cut with sharp claws or scythes"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </div>

        <div className="dseed__field">
          <span className="dseed__label">Rarity</span>
          <div className="dseed__segmented" id="dseed-rarity">
            {RARITIES.map((r) => (
              <button
                key={r.value}
                type="button"
                id={`dseed-rarity-${r.value}`}
                className="dseed__seg"
                data-on={rarity === r.value || undefined}
                onClick={() => setRarity(r.value)}
                title={r.hint}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="dseed__field">
          <span className="dseed__label">Level window</span>
          <div className="dseed__window">
            <div className="dseed__segmented">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  id={`dseed-preset-${p}`}
                  className="dseed__seg"
                  data-on={windowMode === p || undefined}
                  onClick={() => {
                    setWindowMode(p);
                    setLo(PRESET_RANGES[p][0]);
                    setHi(PRESET_RANGES[p][1]);
                  }}
                  title={`L${PRESET_RANGES[p][0]}–${PRESET_RANGES[p][1]}`}
                >
                  {p}
                </button>
              ))}
              <button
                type="button"
                id="dseed-preset-custom"
                className="dseed__seg"
                data-on={windowMode === "custom" || undefined}
                onClick={() => setWindowMode("custom")}
              >
                custom
              </button>
            </div>
            <div className="dseed__range" data-disabled={windowMode !== "custom" || undefined}>
              <input
                id="dseed-lo"
                className="field__input mono dseed__num"
                type="number"
                min={1}
                max={100}
                value={lo}
                disabled={windowMode !== "custom"}
                onChange={(e) => setLo(Number(e.target.value))}
                aria-label="Window minimum level"
              />
              <span aria-hidden="true">–</span>
              <input
                id="dseed-hi"
                className="field__input mono dseed__num"
                type="number"
                min={1}
                max={100}
                value={hi}
                disabled={windowMode !== "custom"}
                onChange={(e) => setHi(Number(e.target.value))}
                aria-label="Window maximum level"
              />
            </div>
          </div>
        </div>

        <label className="dseed__check" htmlFor="dseed-evo">
          <input
            id="dseed-evo"
            type="checkbox"
            checked={includeEvolutions}
            onChange={(e) => setIncludeEvolutions(e.target.checked)}
          />
          Include evolution lines
        </label>

        <div className="dseed__run">
          <button
            type="button"
            id="dseed-distribute"
            className="btn btn--primary"
            disabled={!canRun}
            onClick={() => void handleDistribute()}
          >
            {phase === "running" ? "Distributing…" : "Distribute"}
          </button>
        </div>
      </div>

      {error !== null && (
        <FormError key={error} message={error} citing={null} />
      )}

      {/* --- Results -------------------------------------------------------- */}
      {rows.length > 0 && (
        <>
          {rationale && (
            <p className="dseed__rationale" id="dist-rationale">
              {rationale}
            </p>
          )}
          {warnings.length > 0 && (
            <ul className="dseed__warnings" id="dist-warnings">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}

          <ul id="dist-result-list" className="dist-list" style={{ maxHeight: "none" }}>
            {groups.map(({ lineId, rows: lineRows }) => {
              const relatives = lineRows.filter((r) => !r.matched && !r.already_has);
              const allRelativesOn =
                relatives.length > 0 &&
                relatives.every((r) => selected.has(r.chrooked_id));
              return (
                <li key={lineId} className="dist-group">
                  {relatives.length > 0 && (
                    <label
                      className="dist-group__evo"
                      htmlFor={`dist-evo-${lineId}`}
                      title="Select or deselect this line's other members"
                    >
                      <input
                        id={`dist-evo-${lineId}`}
                        type="checkbox"
                        checked={allRelativesOn}
                        onChange={(e) => toggleLineRelatives(lineRows, e.target.checked)}
                      />
                      evolution line
                    </label>
                  )}
                  <ul className="dist-group__rows">
                    {lineRows.map((row) => (
                      <ResultRow
                        key={row.chrooked_id}
                        row={row}
                        backdropTargetId={backdropTargetId}
                        checked={selected.has(row.chrooked_id)}
                        level={levels.get(row.chrooked_id) ?? row.level}
                        onToggle={() => toggleRow(row.chrooked_id)}
                        onLevel={(v) => setLevel(row.chrooked_id, v)}
                        onRemove={() => setRows((rs) => rs.filter((r) => r !== row))}
                      />
                    ))}
                  </ul>
                </li>
              );
            })}
          </ul>

          <div className="dist-actions" id="dist-actions">
            <span className="dist-actions__dirty" id="dist-selected-count" aria-live="polite">
              {selectedCount} of {selectableCount} selected
            </span>
            <span className="editor-actions__spacer" />
            <button
              type="button"
              id="dist-apply"
              className="btn btn--primary"
              disabled={phase === "applying" || selectedCount === 0}
              onClick={() => void handleApply()}
            >
              {phase === "applying" ? "Applying…" : `Apply (${selectedCount})`}
            </button>
          </div>
        </>
      )}
      </>
      )}
    </section>
  );
}

// --- One result row: checkbox + sprite + name + level + remove. ------------- #

type ResultRowProps = {
  row: DistributeRow;
  backdropTargetId?: string | null;
  checked: boolean;
  level: number;
  onToggle: () => void;
  onLevel: (value: number) => void;
  onRemove: () => void;
};

function ResultRow({
  row,
  backdropTargetId,
  checked,
  level,
  onToggle,
  onLevel,
  onRemove,
}: ResultRowProps) {
  const owned = row.already_has;
  return (
    <li
      id={`dist-row-${row.chrooked_id}`}
      className="dist-row"
      data-dirty={checked && !owned ? "true" : undefined}
      data-owned={owned ? "true" : undefined}
    >
      <input
        id={`dist-check-${row.chrooked_id}`}
        type="checkbox"
        className="dist-row__check"
        checked={checked}
        disabled={owned}
        onChange={onToggle}
        aria-label={`Include ${row.name}`}
      />
      <span className="dist-row__name">
        <DexSprite
          chrookedId={row.chrooked_id}
          dex={row.dex}
          name={row.name}
          backdropTargetId={backdropTargetId}
          size={28}
        />
        <span className="dist-row__name-text">{row.name}</span>
        {!row.matched && !owned && <span className="dist-row__badge">line</span>}
        {owned && <span className="dist-row__badge dist-row__badge--owned">has it</span>}
      </span>

      <div className="dist-row__controls">
        <span className="dist-row__lv-label" aria-hidden="true">
          Lv
        </span>
        <input
          id={`dist-level-${row.chrooked_id}`}
          className="field__input mono dist-row__lv"
          type="number"
          inputMode="numeric"
          min={0}
          max={100}
          disabled={owned}
          value={owned ? "" : level}
          onChange={(e) => onLevel(Number(e.target.value))}
        />
        <button
          type="button"
          id={`dist-remove-${row.chrooked_id}`}
          className="dist-row__remove"
          aria-label={`Remove ${row.name}`}
          onClick={onRemove}
        >
          ×
        </button>
      </div>
    </li>
  );
}
