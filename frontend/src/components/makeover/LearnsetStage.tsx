/* The LEARNSET design stage — the hero diff. Proposes a full learnset via the
   existing suggest Seam, renders current → proposed level-sorted rows with the
   pacing-band annotation behind each proposed row (ac4: a row over its BP band
   gets a mono BAND flag), and lets the author edit a row inline or re-roll (edits
   ride along). LOCK IN writes the anchor's learnset only — the whole-line copy is
   the MIRROR stage's job, the standing wizard stop right after this one (one
   mirror Seam).

   Reuses the pure learnsetDraft machinery (classify, edit, merge) and the
   learnsetBands logic — extends the proposal machinery, never forks it. */

import { useEffect, useMemo, useRef, useState } from "react";
import type { FocusEvent, KeyboardEvent } from "react";
import { api } from "../../api";
import { canonicalize, isKnown } from "../../lib/entityValidation";
import type { LearnsetDraft, LearnsetMove, LoreMode, ProposalAlternative } from "../../types";
import { LoreControl } from "./LoreControl";
import {
  addRow,
  applyAlternative,
  classifyProposed,
  editRow,
  mergeDraft,
  removedRows,
  removeRow,
  swapRowLevels,
} from "../proposal/learnsetDraft";
import {
  bandViolation,
  ladderRungs,
  type LadderRung,
  type LearnsetRubric,
} from "../../lib/learnsetBands";
import { typeSlug } from "../../lib/format";
import { moveNameProps, type MoveMeta } from "../../lib/moveDisplay";
import { StagePanel } from "./StagePanel";
import { MoveCreatePanel } from "./MoveCreatePanel";
import { useMakeoverStage } from "./useMakeoverStage";
import type { CommonStageProps } from "./stageProps";

interface Props extends CommonStageProps {
  moveOptions: readonly string[];
  /** Move display name → base power, for the band annotation. */
  movePower: ReadonlyMap<string, number | null>;
  /** Move name (lowercased) → type + category, for type tint / STAB / italic —
      the same treatment the profile learnset uses. */
  moveMeta: MoveMeta;
  /** The anchor's types — a move matching one is STAB and renders bold. */
  speciesTypes: readonly string[];
  /** The anchor's stronger attacking side — matching moves render italic. */
  attackCategory: "physical" | "special" | null;
  /** The rubric bands (backend-served); null until loaded. */
  rubric: LearnsetRubric | null;
  /** The session's lore sourcing, owned by the workbench (survives stages). */
  loreMode: LoreMode;
  onLoreMode: (mode: LoreMode) => void;
  /** Report the open sub-surface to the overhead rail: "new move" when the inline
      CREATE MOVE panel is open, null otherwise. */
  onSubSurface?: (label: string | null) => void;
  /** Record a move authored mid-learnset so later suggests are steered to use it. */
  onCreated: (name: string, kind: "ability" | "move") => void;
}

export function LearnsetStage(props: Props) {
  const {
    entry,
    initialDirection,
    canLock,
    redirectRef,
    registerActions,
    onLocked,
    onRedirect,
    onPhase,
    moveOptions,
    movePower,
    moveMeta,
    speciesTypes,
    attackCategory,
    rubric,
    loreMode,
    onLoreMode,
    onSubSurface,
    onCreated,
  } = props;

  // The mon's type slugs — a move whose type is in this set is STAB (bold).
  const stab = useMemo(() => new Set(speciesTypes.map(typeSlug)), [speciesTypes]);

  // The at-a-glance BP chip after a move name; status moves (no power) render
  // none. Case-insensitive: learnset rows and the move pool can differ in casing
  // (the same reason moveMeta is keyed lowercased).
  const powerByLower = useMemo(() => {
    const map = new Map<string, number | null>();
    for (const [name, power] of movePower) map.set(name.toLowerCase(), power);
    return map;
  }, [movePower]);
  const bpChip = (move: string) => {
    const bp = movePower.get(move) ?? powerByLower.get(move.toLowerCase());
    // ≤1 is "no fixed power" in the data (0 = status, 1 = variable e.g. Heat
    // Crash) — a number there would mislead, so those rows show no chip.
    return bp != null && bp > 1 ? <span className="mk-lrow__bp mono">{bp}</span> : null;
  };

  // The inline CREATE MOVE panel (the "＋ new move" affordance beside the redirect
  // box). Mutually exclusive with the learnset panel so only one owns the keyboard.
  const [moveCreateOpen, setMoveCreateOpen] = useState(false);
  useEffect(() => {
    onSubSurface?.(moveCreateOpen ? "new move" : null);
    return () => onSubSurface?.(null);
  }, [moveCreateOpen, onSubSurface]);

  // Moves the author demands by name. They ride beside `direction` rather than
  // inside it: the slot skeleton scrubs move names out of the direction prose,
  // so a move named there grew no slot and got silently dropped. The server
  // gives each anchor its own slot. `propose` is recreated every render and the
  // hook's deps include it, so closing over this state is never stale.
  const [anchors, setAnchors] = useState<string[]>([]);

  const hook = useMakeoverStage<LearnsetDraft>({
    section: "learnset",
    entry,
    initialDirection,
    onPhase,
    propose: async (id, direction) => {
      const result = await api.suggestLearnset(id, {
        direction: direction || undefined,
        mode: "full",
        anchors,
        lore: loreMode,
      });
      return {
        draft: result.draft,
        rationale: result.rationale ?? {},
        alternatives: (result.alternatives ?? []) as ProposalAlternative[],
        warnings: result.warnings,
        // A flagged draft (soft bound tripped) still comes back editable — show it
        // with the reason banner instead of a bare NO PROPOSAL.
        error: result.error,
      };
    },
    merge: (raw, draft) => mergeDraft(raw, draft),
    // Writes the anchor only — the whole-line copy is the MIRROR stage's job.
    onLocked: () => onLocked({}),
    onRedirect,
  });

  const draft = hook.draft;
  const proposed = useMemo(() => draft?.learnset ?? [], [draft]);
  const classified = classifyProposed(entry.learnset, proposed);
  const dropped = removedRows(entry.learnset, proposed);

  // A dropped anchor is the failure that prompted the whole field, so it gets
  // its own loud banner above the rows instead of the polite list under them.
  const anchorWarnings = useMemo(
    () => hook.warnings.filter((w) => w.startsWith(ANCHOR_PREFIX)),
    [hook.warnings],
  );
  const crowdedWarnings = useMemo(
    () => hook.warnings.filter((w) => w.startsWith(CROWDED_PREFIX)),
    [hook.warnings],
  );
  const otherWarnings = useMemo(
    () =>
      hook.warnings.filter(
        (w) => !w.startsWith(ANCHOR_PREFIX) && !w.startsWith(CROWDED_PREFIX),
      ),
    [hook.warnings],
  );

  const [editingKey, setEditingKey] = useState<string | null>(null);
  // Level-swap (#90): tap ⇅ on one row to arm it, tap a second row to exchange
  // their levels. Two taps, no drag — a drag target is unhittable on a handheld,
  // and a remove-plus-two-re-adds loses the ladder position it was checking.
  const [swapFromKey, setSwapFromKey] = useState<string | null>(null);

  function swapWith(rowKey: string) {
    if (swapFromKey === null) {
      setSwapFromKey(rowKey);
      return;
    }
    if (swapFromKey === rowKey) {
      setSwapFromKey(null);
      return;
    }
    const [aLv, ...aMove] = swapFromKey.split("-");
    const [bLv, ...bMove] = rowKey.split("-");
    const a = draftIndexOf(Number(aLv), aMove.join("-"));
    const b = draftIndexOf(Number(bLv), bMove.join("-"));
    if (a >= 0 && b >= 0) hook.editDraft(swapRowLevels(draft, a, b));
    setSwapFromKey(null);
  }
  // The ladder overlay: off by default — the list reads calm until the author
  // asks to see the pacing structure the rows sit in.
  const [ladderOn, setLadderOn] = useState(false);
  const rungs = useMemo(() => ladderRungs(rubric), [rubric]);

  // With the overlay on, rows are dealt into their rung so the ladder reads as
  // structure rather than as a per-row annotation. A rung with no rows still
  // renders — the gap IS the information. L0 rows sit above the ladder: they are
  // on-evolution rewards and the bands never governed them.
  const rungGroups: { rung: LadderRung | null; rows: typeof classified }[] =
    ladderOn && rungs.length > 0 && classified.length > 0
      ? [
          { rung: null, rows: classified.filter(({ row }) => row.level === 0) },
          ...rungs.map((rung) => ({
            rung,
            rows: classified.filter(
              ({ row }) => row.level >= rung.levelMin && row.level <= rung.levelMax,
            ),
          })),
        ].filter((group) => group.rung !== null || group.rows.length > 0)
      : [{ rung: null, rows: classified }];

  function draftIndexOf(level: number, move: string): number {
    return proposed.findIndex((m) => m.level === level && m.move === move);
  }

  function removeRowByKey(rowKey: string) {
    const [lvStr, ...moveParts] = rowKey.split("-");
    const index = draftIndexOf(Number(lvStr), moveParts.join("-"));
    if (index >= 0) hook.editDraft(removeRow(draft, index));
    if (editingKey === rowKey) setEditingKey(null);
  }

  // ArrowUp/Down move row focus within the proposed list; `e` opens the focused
  // row's editor, `d`/Delete removes it. Enter is left to bubble to the workbench
  // (LOCK IN).
  function handleListKey(event: KeyboardEvent<HTMLOListElement>) {
    const isNav = event.key === "ArrowDown" || event.key === "ArrowUp";
    const isEdit = event.key === "e";
    const isDelete = event.key === "d" || event.key === "Delete" || event.key === "Backspace";
    if (!isNav && !isEdit && !isDelete) return;
    const rows = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(".mk-lrow"));
    const active = document.activeElement as HTMLElement | null;
    const index = rows.findIndex((r) => r === active);
    const key = active?.dataset.rowkey;
    if (isEdit) {
      if (key) {
        event.preventDefault();
        setEditingKey(key);
      }
      return;
    }
    if (isDelete) {
      if (key) {
        event.preventDefault();
        // Focus the neighbour so the keyboard flow survives the removal.
        rows[index + 1 < rows.length ? index + 1 : index - 1]?.focus();
        removeRowByKey(key);
      }
      return;
    }
    event.preventDefault();
    const nextIndex =
      index === -1 ? 0 : (index + (event.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length;
    rows[nextIndex]?.focus();
  }

  // The CURRENT column, reused verbatim in both phases so it never shifts on load
  // → proposal (ac: stable two-pane). `marks` flags dropped rows (empty pre-proposal).
  const currentColumn = (marks: readonly LearnsetMove[]) => (
    <div className="mk-col">
      <p className="mk-col__head mono">current</p>
      <ol className="mk-learnset">
        {entry.learnset.length === 0 && <li className="mk-empty mono">no level-up moves</li>}
        {[...entry.learnset]
          .sort((a, b) => a.level - b.level || a.move.localeCompare(b.move))
          .map((m, i) => {
            const isDropped = marks.some((d) => d.level === m.level && d.move === m.move);
            return (
              <li key={`cur-${m.level}-${m.move}-${i}`} className="mk-lrow" data-removed={isDropped || undefined}>
                <span className="mk-lrow__lv mono">{m.level === 0 ? "—" : `L${m.level}`}</span>
                <span className="mk-lrow__move" {...moveNameProps(m.move, moveMeta, stab, attackCategory)}>
                  {m.move}
                </span>
                {bpChip(m.move)}
                {isDropped && <span className="mk-lrow__mark mono">→ removed</span>}
              </li>
            );
          })}
      </ol>
    </div>
  );

  if (moveCreateOpen) {
    return (
      <div className="mk-stage" id="mk-stage-learnset-movecreate">
        <button
          type="button"
          className="mk-btn mk-btn--ghost mono"
          id="mk-learnset-movecreate-back"
          onClick={() => setMoveCreateOpen(false)}
        >
          ← back to learnset
        </button>
        <MoveCreatePanel
          redirectRef={redirectRef}
          registerActions={registerActions}
          onCreated={onCreated}
          onClose={() => setMoveCreateOpen(false)}
        />
      </div>
    );
  }

  return (
    <StagePanel
      stageLabel="LEARNSET"
      hook={hook}
      canLock={canLock}
      placeholder="steer the learnset (e.g. special-attack leaning)…"
      redirectRef={redirectRef}
      registerActions={registerActions}
      extraControl={
        <>
          <LoreControl
            mode={loreMode}
            onChange={onLoreMode}
            disabled={hook.phase === "proposing"}
          />
          <AnchorField
            moveOptions={moveOptions}
            anchors={anchors}
            onChange={setAnchors}
            disabled={hook.phase === "proposing"}
          />
          <button
            type="button"
            className="mk-btn mk-btn--ghost mono"
            id="mk-learnset-ladder-toggle"
            aria-pressed={ladderOn}
            disabled={rungs.length === 0}
            title="Show the pacing-band rungs the rows sit on"
            onClick={() => setLadderOn((on) => !on)}
          >
            {ladderOn ? "LADDER ON" : "LADDER"}
          </button>
          <button
            type="button"
            className="mk-btn mk-btn--ghost mono"
            id="mk-learnset-new-move"
            title="Author a new move to use in this learnset"
            onClick={() => setMoveCreateOpen(true)}
          >
            ＋ new move
          </button>
        </>
      }
      applyAlternative={(alt, current) => applyAlternative(current, alt, moveOptions)}
      altLabel={(value) => (Array.isArray(value) ? `${value.length} moves` : String(value))}
      current={
        // Two-pane from load: CURRENT holds the left cell; the right cell is an
        // empty PROPOSED placeholder until a learnset is generated (no auto-fire).
        <div className="mk-cols mk-cols--learnset">
          {currentColumn([])}
          <div className="mk-col">
            <p className="mk-col__head mono">proposed</p>
            <p className="mk-empty mono" id="mk-learnset-proposed-empty">
              no learnset yet — PROPOSE to generate
            </p>
            {/* Static row ghosts balance the two panes pre-generation (not a
                loading signal — the shimmer stays reserved for proposing). */}
            <div className="mk-skel-static" aria-hidden="true">
              <span className="mk-skel-row" />
              <span className="mk-skel-row" />
              <span className="mk-skel-row" />
              <span className="mk-skel-row" />
            </div>
          </div>
        </div>
      }
    >
      {anchorWarnings.length > 0 && (
        <div className="mk-anchor-alert" id="mk-learnset-anchor-alert" role="alert">
          <p className="mk-anchor-alert__head mono">dropped anchors</p>
          <ul className="mk-anchor-alert__list">
            {anchorWarnings.map((warning, i) => (
              <li key={i} className="mono">
                {warning.slice(ANCHOR_PREFIX.length)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {crowdedWarnings.length > 0 && (
        <div className="mk-crowded-note" id="mk-learnset-crowded" role="status">
          <p className="mk-crowded-note__head mono">what this cost</p>
          <ul className="mk-crowded-note__list">
            {crowdedWarnings.map((warning, i) => (
              <li key={i} className="mono">
                {warning.slice(CROWDED_PREFIX.length)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mk-cols mk-cols--learnset">
        {currentColumn(dropped)}

        <div className="mk-col">
          <p className="mk-col__head mono">proposed</p>
          <ol className="mk-learnset" data-ladder={ladderOn || undefined} onKeyDown={handleListKey}>
            {classified.length === 0 && <li className="mk-empty mono">no proposed moves</li>}
            {rungGroups.map(({ rung, rows }) => (
              <li key={rung ? `rung-${rung.levelMin}` : "rung-none"} className="mk-runggroup">
                {rung !== null && (
                  <p className="mk-rung mono" data-empty={rows.length === 0 || undefined}>
                    <span className="mk-rung__lv">
                      L{rung.levelMin}–{rung.levelMax}
                    </span>
                    <span className="mk-rung__rule" aria-hidden="true" />
                    <span className="mk-rung__bp">{rungWindow(rung)}</span>
                  </p>
                )}
                <ol className="mk-runggroup__rows">
                  {rows.map(({ row, status }) => {
              const rowKey = `${row.level}-${row.move}`;
              const changed = status === "added";
              const violation = bandViolation(rubric, row.level, movePower.get(row.move) ?? null);
              const isEditing = editingKey === rowKey;
              const draftIndex = draftIndexOf(row.level, row.move);
              return (
                <li
                  key={rowKey}
                  className="mk-lrow mk-lrow--proposed"
                  data-rowkey={rowKey}
                  data-changed={changed || undefined}
                  data-violation={violation !== null || undefined}
                  data-swap-armed={swapFromKey === rowKey || undefined}
                  data-swap-target={
                    (swapFromKey !== null && swapFromKey !== rowKey) || undefined
                  }
                  tabIndex={0}
                  onDoubleClick={() => setEditingKey(rowKey)}
                >
                  {isEditing ? (
                    <RowEditor
                      level={row.level}
                      move={row.move}
                      moveOptions={moveOptions}
                      onCommit={(patch) => {
                        if (draftIndex >= 0) hook.editDraft(editRow(draft, draftIndex, patch));
                        setEditingKey(null);
                      }}
                      onRemove={() => removeRowByKey(rowKey)}
                      onCancel={() => setEditingKey(null)}
                    />
                  ) : (
                    <>
                      <span className="mk-lrow__lv mono">{row.level === 0 ? "—" : `L${row.level}`}</span>
                      <span className="mk-lrow__move" {...moveNameProps(row.move, moveMeta, stab, attackCategory)}>
                        {row.move}
                      </span>
                      {bpChip(row.move)}
                      {changed && <span className="mk-lrow__mark mono">→ new</span>}
                      {violation && <span className="mk-lrow__band mono">{violation}</span>}
                      <button
                        type="button"
                        className="mk-lrow__swap mono"
                        aria-label={
                          swapFromKey === null
                            ? `Swap the level of ${row.move} with another row`
                            : swapFromKey === rowKey
                              ? `Cancel swapping ${row.move}`
                              : `Swap levels with ${row.move}`
                        }
                        aria-pressed={swapFromKey === rowKey}
                        title={
                          swapFromKey === null
                            ? "Swap this move's level with another row"
                            : swapFromKey === rowKey
                              ? "Cancel the swap"
                              : "Swap levels with this row"
                        }
                        onClick={() => swapWith(rowKey)}
                      >
                        {swapFromKey !== null && swapFromKey !== rowKey ? "swap here" : "⇅"}
                      </button>
                      <button
                        type="button"
                        className="mk-lrow__edit mono"
                        aria-label={`Edit ${row.move}`}
                        onClick={() => setEditingKey(rowKey)}
                      >
                        edit
                      </button>
                      <button
                        type="button"
                        className="mk-lrow__remove mono"
                        aria-label={`Remove ${row.move}`}
                        title={`Remove ${row.move}`}
                        onClick={() => removeRowByKey(rowKey)}
                      >
                        ✕
                      </button>
                    </>
                  )}
                </li>
              );
                  })}
                </ol>
              </li>
            ))}
          </ol>
          <AddRow
            moveOptions={moveOptions}
            onAdd={(level, move) => hook.editDraft(addRow(draft, { level, move }))}
          />
        </div>
      </div>

      {otherWarnings.length > 0 && (
        <ul className="mk-slot-warnings" id="mk-learnset-warnings">
          {otherWarnings.map((warning, i) => (
            <li key={i} className="mk-slot-warning mono" role="status">
              {warning}
            </li>
          ))}
        </ul>
      )}
    </StagePanel>
  );
}

/** A rung's BP window, spelled from the numbers rather than the band label —
    the label is prose the flag reuses, the numbers are what the check enforces. */
function rungWindow(rung: LadderRung): string {
  if (rung.bpMin !== undefined && rung.bpMax !== undefined) return `${rung.bpMin}–${rung.bpMax}BP`;
  if (rung.bpMax !== undefined) return `≤${rung.bpMax}BP`;
  if (rung.bpMin !== undefined) return `${rung.bpMin}+BP`;
  return rung.label;
}

/** The server tags a dropped-anchor warning with this prefix, alongside its
    existing `pacing: ` and `auto-repair: ` tags. */
const ANCHOR_PREFIX = "anchor: ";
/** A slot the skeleton had to give up because something else claimed its space
    — usually an anchor. Distinct from `anchor: `: nothing failed, but the
    author paid a price they never saw. */
const CROWDED_PREFIX = "crowded: ";

interface AnchorFieldProps {
  moveOptions: readonly string[];
  anchors: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}

/** The ANCHORS control beside PROPOSE: moves the author demands by name, each
    of which the server turns into its own skeleton slot. Chips plus a datalist
    input, gated against the pool the same way AddRow is.

    This lives INSIDE StagePanel's direction <form>, whose submit fires a
    proposal — so the button is type="button" and Enter is swallowed here, or
    naming an anchor would launch a call instead of adding a chip. */
function AnchorField({ moveOptions, anchors, onChange, disabled }: AnchorFieldProps) {
  const [draft, setDraft] = useState("");
  const canon = canonicalize(draft, moveOptions);
  const known = canon.trim() !== "" && isKnown(canon, moveOptions);
  const isDuplicate =
    known && anchors.some((a) => a.toLowerCase() === canon.trim().toLowerCase());

  function commit() {
    if (!known || isDuplicate) return;
    onChange([...anchors, canon.trim()]);
    setDraft("");
  }

  return (
    <div className="mk-anchors" id="mk-learnset-anchors">
      <label className="mk-anchors__label mono" htmlFor="mk-anchor-input">
        anchors
      </label>
      {anchors.map((anchor) => (
        <span key={anchor} className="mk-anchors__chip mono">
          {anchor}
          <button
            type="button"
            className="mk-anchors__drop"
            aria-label={`Remove anchor ${anchor}`}
            disabled={disabled}
            onClick={() => onChange(anchors.filter((a) => a !== anchor))}
          >
            ✕
          </button>
        </span>
      ))}
      <input
        className="mk-anchors__input mono"
        id="mk-anchor-input"
        type="text"
        list="mk-anchor-move-list"
        placeholder="must-have move…"
        value={draft}
        disabled={disabled}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            commit();
          }
        }}
        autoComplete="off"
      />
      <datalist id="mk-anchor-move-list">
        {moveOptions.map((opt) => (
          <option key={opt} value={opt} />
        ))}
      </datalist>
      <button
        type="button"
        className="mk-btn mk-btn--ghost"
        id="mk-learnset-anchor-add"
        disabled={disabled || !known || isDuplicate}
        title={
          isDuplicate
            ? "Already an anchor"
            : known
              ? "Require this move in the proposal"
              : "Type a known move name"
        }
        onClick={commit}
      >
        ＋ anchor
      </button>
    </div>
  );
}

interface AddRowProps {
  moveOptions: readonly string[];
  onAdd: (level: number, move: string) => void;
}

/** The "＋ add move" control under the proposed list: a level input + a move
    datalist that appends a new (level, move) row. Disabled until the move name
    resolves against the pool (isKnown), mirroring the RowEditor's guard. */
function AddRow({ moveOptions, onAdd }: AddRowProps) {
  const [lv, setLv] = useState("1");
  const [mv, setMv] = useState("");
  const canon = canonicalize(mv, moveOptions);
  const known = canon.trim() !== "" && isKnown(canon, moveOptions);

  function commit() {
    if (!known) return;
    const parsed = Number(lv);
    const level = Number.isFinite(parsed) ? Math.min(100, Math.max(0, Math.round(parsed))) : 0;
    onAdd(level, canon.trim());
    setMv("");
  }

  return (
    <div className="mk-lrow-add" id="mk-learnset-add">
      <input
        className="mk-lrow__lv-input mono"
        type="number"
        min={0}
        max={100}
        aria-label="New move level"
        value={lv}
        onChange={(e) => setLv(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          }
        }}
      />
      <input
        className="mk-lrow__move-input mono"
        type="text"
        list="mk-add-move-list"
        aria-label="New move"
        placeholder="add a move…"
        value={mv}
        onChange={(e) => setMv(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          }
        }}
        autoComplete="off"
      />
      <datalist id="mk-add-move-list">
        {moveOptions.map((opt) => (
          <option key={opt} value={opt} />
        ))}
      </datalist>
      <button
        type="button"
        className="mk-btn mk-btn--ghost"
        id="mk-learnset-add-btn"
        disabled={!known}
        title={known ? "Add this move" : "Type a known move name"}
        onClick={commit}
      >
        ＋ add move
      </button>
    </div>
  );
}

interface RowEditorProps {
  level: number;
  move: string;
  moveOptions: readonly string[];
  onCommit: (patch: { level: number; move: string }) => void;
  onRemove: () => void;
  onCancel: () => void;
}

function RowEditor({ level, move, moveOptions, onCommit, onRemove, onCancel }: RowEditorProps) {
  const [lv, setLv] = useState(String(level));
  const [mv, setMv] = useState(move);
  const [error, setError] = useState<string | null>(null);
  // Escape means discard, so it has to suppress the commit-on-blur that firing
  // onCancel would otherwise trigger as focus leaves.
  const discarded = useRef(false);

  function cancel() {
    discarded.current = true;
    onCancel();
  }

  function commit() {
    const canon = canonicalize(mv, moveOptions);
    if (canon.trim() !== "" && !isKnown(canon, moveOptions)) {
      setError("Unknown move");
      return;
    }
    const parsed = Number(lv);
    onCommit({
      level: Number.isFinite(parsed) ? parsed : level,
      move: canon.trim() === "" ? move : canon,
    });
  }

  // Tapping away used to discard the edit silently — the author's reported
  // "I hit confirm and often miss it". Focus leaving the editor entirely now
  // commits, so the only way to lose an edit is to ask for it with Escape.
  function commitOnFocusLeave(event: FocusEvent<HTMLSpanElement>) {
    if (discarded.current) return;
    const next = event.relatedTarget as Node | null;
    if (next && event.currentTarget.contains(next)) return;
    commit();
  }

  return (
    <span className="mk-lrow__editor" onBlur={commitOnFocusLeave}>
      <input
        className="mk-lrow__lv-input mono"
        type="number"
        min={0}
        max={100}
        aria-label="Level"
        value={lv}
        autoFocus
        onChange={(e) => setLv(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          }
          if (e.key === "Escape") cancel();
        }}
      />
      <input
        className="mk-lrow__move-input mono"
        type="text"
        list="mk-move-list"
        aria-label="Move"
        aria-invalid={error ? "true" : undefined}
        value={mv}
        onChange={(e) => {
          setMv(e.target.value);
          setError(null);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          }
          if (e.key === "Escape") cancel();
        }}
      />
      <datalist id="mk-move-list">
        {moveOptions.map((opt) => (
          <option key={opt} value={opt} />
        ))}
      </datalist>
      {error && (
        <span className="mk-lrow__error mono" role="alert">
          {error}
        </span>
      )}
      <button
        type="button"
        className="mk-lrow__commit mono"
        aria-label="Save row"
        title="Save (leaving the row saves too; Escape discards)"
        onClick={commit}
      >
        ✓
      </button>
      <button
        type="button"
        className="mk-lrow__remove mono"
        aria-label="Remove row"
        title="Remove this move"
        onClick={onRemove}
      >
        ✕
      </button>
    </span>
  );
}
