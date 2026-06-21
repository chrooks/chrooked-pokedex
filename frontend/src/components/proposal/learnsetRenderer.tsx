/* The learnset section renderer (#7) — the hero diff. Current │ proposed as
   level-sorted rows. Proposed rows added vs current read in provisional amber
   with a `→ new` marker; dropped current rows show struck as `removed`. A
   proposed row's (level, move) is editable inline — Enter (or double-click) opens
   the editor, change autosorts the list level-ascending. Reasoning shows per row.

   A thin React shell over the pure logic in learnsetDraft.ts — the shell stays
   section-agnostic; all the learnset knowledge lives here. */

import { useState } from "react";
import type { LearnsetDraft } from "../../types";
import type { CellRenderArgs, SectionRenderer } from "./renderer";
import {
  applyAlternative,
  classifyProposed,
  currentLearnset,
  editRow,
  mergeDraft,
  removedRows,
} from "./learnsetDraft";

/** Build the learnset renderer. No external pool needed (free-text moves). */
export function learnsetRenderer(): SectionRenderer<LearnsetDraft> {
  return {
    id: "learnset",
    title: "Learnset",
    suggestLabel: "Suggest a learnset with the LLM",
    placeholder: "how would you like to change the learnset?",
    renderCells: (args) => <LearnsetCells {...args} />,
    applyAlternative,
    mergeDraft,
  };
}

function LearnsetCells({
  entry,
  draft,
  rationale,
  onEdit,
}: CellRenderArgs<LearnsetDraft>) {
  const current = currentLearnset(entry);
  const proposed = draft?.learnset ?? [];
  const classified = classifyProposed(current, proposed);
  const dropped = removedRows(current, proposed);
  const sectionReason = rationale.learnset;

  // Index into the *sorted* proposed list that is open for editing, or null.
  const [editingKey, setEditingKey] = useState<string | null>(null);
  // Which row's reasoning is expanded (Progressive Disclosure — rows stay one
  // line so current↔proposed align and the diff is scannable; the reasoning is
  // on demand, keyboard-reachable, and also revealed on hover via CSS).
  const [openReason, setOpenReason] = useState<string | null>(null);

  // Find a row's index in the draft's (unsorted) array by identity so an edit
  // patches the right element even after autosort reorders the display.
  function draftIndexOf(level: number, move: string): number {
    return proposed.findIndex((m) => m.level === level && m.move === move);
  }

  return (
    <>
      <div className="proposal__col">
        <p className="proposal__col-head">Current</p>
        <ol className="ledger__learnset proposal__learnset">
          {current.length === 0 && (
            <li className="lrow__empty">No level-up moves.</li>
          )}
          {[...current]
            .sort((a, b) => a.level - b.level || a.move.localeCompare(b.move))
            .map((m, i) => {
              const isDropped = dropped.some(
                (d) => d.level === m.level && d.move === m.move,
              );
              return (
                <li
                  key={`cur-${m.level}-${m.move}-${i}`}
                  className="ledger__move"
                  data-removed={isDropped}
                >
                  <span className="ledger__move-lv mono">
                    {m.level === 0 ? "—" : `L${m.level}`}
                  </span>
                  <span className="ledger__move-name">{m.move}</span>
                  {isDropped && (
                    <span className="proposal-cell__marker mono">→ removed</span>
                  )}
                </li>
              );
            })}
        </ol>
      </div>

      <div className="proposal__col">
        <p className="proposal__col-head">Proposed</p>
        <ol className="ledger__learnset proposal__learnset">
          {classified.length === 0 && (
            <li className="lrow__empty">No proposed moves.</li>
          )}
          {classified.map(({ row, status }) => {
            const rowKey = `${row.level}-${row.move}`;
            const isEditing = editingKey === rowKey;
            const changed = status === "added";
            const draftIndex = draftIndexOf(row.level, row.move);
            const reasonOpen = openReason === rowKey;
            const reasonId = `proposal-learnset-why-${rowKey}`;
            return (
              <li
                key={rowKey}
                className="proposal__prow-wrap"
              >
                <div
                  className={`ledger__move proposal__prow${changed ? " proposal-cell--changed" : ""}`}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      setEditingKey(isEditing ? null : rowKey);
                    }
                  }}
                  onDoubleClick={() => setEditingKey(rowKey)}
                >
                  {isEditing ? (
                    <ProposedRowEditor
                      level={row.level}
                      move={row.move}
                      onCommit={(patch) => {
                        if (draftIndex >= 0)
                          onEdit(editRow(draft, draftIndex, patch));
                        setEditingKey(null);
                      }}
                      onCancel={() => setEditingKey(null)}
                    />
                  ) : (
                    <>
                      <span className="ledger__move-lv mono">
                        {row.level === 0 ? "—" : `L${row.level}`}
                      </span>
                      <span className="ledger__move-name">{row.move}</span>
                      {changed && (
                        <span className="proposal-cell__marker mono">→ new</span>
                      )}
                      {row.reasoning && (
                        <button
                          type="button"
                          className="proposal__why"
                          aria-expanded={reasonOpen}
                          aria-controls={reasonId}
                          title="Why this move?"
                          onClick={() =>
                            setOpenReason(reasonOpen ? null : rowKey)
                          }
                        >
                          why
                        </button>
                      )}
                    </>
                  )}
                </div>
                {row.reasoning && !isEditing && (
                  <p
                    id={reasonId}
                    className="proposal-cell__rationale proposal__prow-why"
                    hidden={!reasonOpen}
                  >
                    {row.reasoning}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
        {sectionReason && (
          <details className="proposal__why-design">
            <summary className="proposal__why-design-summary">
              Why this design
            </summary>
            <p className="proposal-cell__rationale proposal__why-design-body">
              {sectionReason}
            </p>
          </details>
        )}
      </div>
    </>
  );
}

interface EditorProps {
  level: number;
  move: string;
  onCommit: (patch: { level: number; move: string }) => void;
  onCancel: () => void;
}

/** Inline (level, move) editor for one proposed row. Commit autosorts the list. */
function ProposedRowEditor({ level, move, onCommit, onCancel }: EditorProps) {
  const [lv, setLv] = useState(String(level));
  const [mv, setMv] = useState(move);

  function commit() {
    const parsed = Number(lv);
    onCommit({
      level: Number.isFinite(parsed) ? parsed : level,
      move: mv.trim() === "" ? move : mv,
    });
  }

  return (
    <span className="proposal__row-editor">
      <input
        className="proposal__row-level mono"
        type="number"
        min={0}
        max={100}
        aria-label="Level"
        value={lv}
        autoFocus
        onChange={(e) => setLv(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") onCancel();
        }}
      />
      <input
        className="proposal__row-move mono"
        type="text"
        aria-label="Move"
        value={mv}
        onChange={(e) => setMv(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") onCancel();
        }}
      />
      <button
        type="button"
        className="proposal__row-commit"
        aria-label="Save row"
        onClick={commit}
      >
        ✓
      </button>
    </span>
  );
}
