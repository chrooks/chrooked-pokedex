/* The LEARNSET design stage — the hero diff. Proposes a full learnset via the
   existing suggest Seam, renders current → proposed level-sorted rows with the
   pacing-band annotation behind each proposed row (ac4: a row over its BP band
   gets a mono BAND flag), lets the author edit a row inline or re-roll (edits ride
   along), and shows the WHOLE-LINE mirror-down preview (pre-evos = anchor minus
   L0) before any write (ac5). LOCK IN writes the anchor's learnset AND mirrors the
   kit down to every pre-evo through the existing CRUD route.

   Reuses the pure learnsetDraft machinery (classify, edit, merge) and the
   learnsetBands + mirrorDown logic — extends the proposal machinery, never forks
   it. */

import { useMemo, useState } from "react";
import type { KeyboardEvent } from "react";
import { api } from "../../api";
import { isKnown } from "../../lib/entityValidation";
import type { LearnsetDraft, LearnsetMove, ProposalAlternative } from "../../types";
import {
  applyAlternative,
  classifyProposed,
  editRow,
  mergeDraft,
  removedRows,
  removeRow,
} from "../proposal/learnsetDraft";
import { bandViolation, type LearnsetRubric } from "../../lib/learnsetBands";
import { mirrorDownPreview, preEvos } from "../../lib/mirrorDown";
import { writeMirror } from "./mirrorWrite";
import { MirrorRowList } from "./MirrorRowList";
import { StagePanel } from "./StagePanel";
import { useMakeoverStage } from "./useMakeoverStage";
import type { CommonStageProps } from "./stageProps";
import type { DexEntry } from "../../types";

interface Props extends CommonStageProps {
  moveOptions: readonly string[];
  /** Move display name → base power, for the band annotation. */
  movePower: ReadonlyMap<string, number | null>;
  /** The rubric bands (backend-served); null until loaded. */
  rubric: LearnsetRubric | null;
  /** The whole dex by chrooked_id, for the mirror-down line resolution. */
  byId: ReadonlyMap<string, DexEntry>;
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
    moveOptions,
    movePower,
    rubric,
    byId,
  } = props;

  const line = useMemo(() => preEvos(entry, byId), [entry, byId]);
  // Pre-evos the author has opted OUT of mirroring to (by chrooked_id). Declared
  // before the hook so extraWrites / onLocked close over the current set.
  const [excludedPreEvos, setExcludedPreEvos] = useState<ReadonlySet<string>>(new Set());

  function togglePreEvo(chrookedId: string) {
    setExcludedPreEvos((prev) => {
      const next = new Set(prev);
      if (next.has(chrookedId)) next.delete(chrookedId);
      else next.add(chrookedId);
      return next;
    });
  }

  const hook = useMakeoverStage<LearnsetDraft>({
    section: "learnset",
    entry,
    initialDirection,
    propose: async (id, direction) => {
      const result = await api.suggestLearnset(id, { direction: direction || undefined, mode: "full" });
      return {
        draft: result.draft,
        rationale: result.rationale ?? {},
        alternatives: (result.alternatives ?? []) as ProposalAlternative[],
      };
    },
    merge: (raw, draft) => mergeDraft(raw, draft),
    extraWrites: async (draft) => {
      // Mirror the anchor kit down to every INCLUDED pre-evo: same typing +
      // abilities, the anchor learnset minus L0. A pre-evo the author skipped is
      // left untouched. Silent so the workbench flushes ONE dex refresh.
      const learnset: LearnsetMove[] = draft.learnset.map((r) => ({ level: r.level, move: r.move }));
      const kit = { types: entry.types, abilities: entry.abilities, learnset };
      const targets = mirrorDownPreview(entry, byId, kit).filter(
        (row) => !excludedPreEvos.has(row.chrooked_id),
      );
      await writeMirror(targets);
    },
    // The learnset lock writes the anchor's learnset AND every INCLUDED pre-evo
    // copy — the read-back tail checks exactly what was written.
    onLocked: () =>
      onLocked({}, [
        entry.chrooked_id,
        ...line.map((m) => m.chrooked_id).filter((id) => !excludedPreEvos.has(id)),
      ]),
    onRedirect,
  });

  const draft = hook.draft;
  const proposed = useMemo(() => draft?.learnset ?? [], [draft]);
  const classified = classifyProposed(entry.learnset, proposed);
  const dropped = removedRows(entry.learnset, proposed);

  const [editingKey, setEditingKey] = useState<string | null>(null);

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

  return (
    <StagePanel
      stageLabel="LEARNSET"
      hook={hook}
      canLock={canLock}
      placeholder="steer the learnset (e.g. special-attack leaning)…"
      redirectRef={redirectRef}
      registerActions={registerActions}
      applyAlternative={(alt, current) => applyAlternative(current, alt)}
      altLabel={(value) => (Array.isArray(value) ? `${value.length} moves` : String(value))}
    >
      <div className="mk-cols mk-cols--learnset">
        <div className="mk-col">
          <p className="mk-col__head mono">current</p>
          <ol className="mk-learnset">
            {entry.learnset.length === 0 && <li className="mk-empty mono">no level-up moves</li>}
            {[...entry.learnset]
              .sort((a, b) => a.level - b.level || a.move.localeCompare(b.move))
              .map((m, i) => {
                const isDropped = dropped.some((d) => d.level === m.level && d.move === m.move);
                return (
                  <li key={`cur-${m.level}-${m.move}-${i}`} className="mk-lrow" data-removed={isDropped || undefined}>
                    <span className="mk-lrow__lv mono">{m.level === 0 ? "—" : `L${m.level}`}</span>
                    <span className="mk-lrow__move">{m.move}</span>
                    {isDropped && <span className="mk-lrow__mark mono">→ removed</span>}
                  </li>
                );
              })}
          </ol>
        </div>

        <div className="mk-col">
          <p className="mk-col__head mono">proposed</p>
          <ol className="mk-learnset" onKeyDown={handleListKey}>
            {classified.length === 0 && <li className="mk-empty mono">no proposed moves</li>}
            {classified.map(({ row, status }) => {
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
                      <span className="mk-lrow__move">{row.move}</span>
                      {changed && <span className="mk-lrow__mark mono">→ new</span>}
                      {violation && <span className="mk-lrow__band mono">{violation}</span>}
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
        </div>
      </div>

      {hook.warnings.length > 0 && (
        <ul className="mk-slot-warnings" id="mk-learnset-warnings">
          {hook.warnings.map((warning, i) => (
            <li key={i} className="mk-slot-warning mono" role="status">
              {warning}
            </li>
          ))}
        </ul>
      )}

      {draft !== null && line.length > 0 && (
        <details className="mk-mirror" id="mk-mirror-down" open>
          <summary className="mk-mirror__summary mono">
            mirror-down · {line.length - excludedPreEvos.size}/{line.length} pre-evo
            {line.length === 1 ? "" : "s"} (types + abilities + learnset − L0) · toggle to skip
          </summary>
          <MirrorRowList
            rows={mirrorDownPreview(entry, byId, {
              types: entry.types,
              abilities: entry.abilities,
              learnset: proposed.map((r) => ({ level: r.level, move: r.move })),
            })}
            excluded={excludedPreEvos}
            onToggle={togglePreEvo}
          />
        </details>
      )}
    </StagePanel>
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

  function commit() {
    if (mv.trim() !== "" && !isKnown(mv, moveOptions)) {
      setError("Unknown move");
      return;
    }
    const parsed = Number(lv);
    onCommit({
      level: Number.isFinite(parsed) ? parsed : level,
      move: mv.trim() === "" ? move : mv,
    });
  }

  return (
    <span className="mk-lrow__editor">
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
          if (e.key === "Escape") onCancel();
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
          if (e.key === "Escape") onCancel();
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
      <button type="button" className="mk-lrow__commit mono" aria-label="Save row" onClick={commit}>
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
