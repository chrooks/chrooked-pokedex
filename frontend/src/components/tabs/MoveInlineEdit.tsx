/* Right-click inline editing for the Moves table — the move sibling of the dex
   table's InlineEditMenu (same popover chrome, reusing the dex-edit__* styles).

   Moves are stored whole, not as Overrides, so the save path is simpler than
   the species one: strip the server-computed merge-view flags off the loaded
   move, replace ONE field, PUT the record. Every behaviour-carrying field
   (effect / argument / additional_effects / aka) rides along untouched. */

import { useState } from "react";
import type { Move, MoveWrite } from "../../types";
import { TypeSelect } from "../TypeSelect";
import { CategorySelect } from "../CategorySelect";
import { TargetGridField } from "../TargetGrid";
import "../dex-table.css";

export type MoveInlineField =
  | "type"
  | "category"
  | "power"
  | "accuracy"
  | "pp"
  | "target";

export const MOVE_INLINE_LABEL: Record<MoveInlineField, string> = {
  type: "Type",
  category: "Category",
  power: "Power",
  accuracy: "Accuracy",
  pp: "PP",
  target: "Target",
};

/** The loaded merge-view move as its writable PUT shape: drop the two
    server-recomputed keys the loader rejects (422), keep everything else. */
export function toMoveWrite(move: Move): MoveWrite {
  const { overridden_fields: _fields, base: _base, ...write } = move;
  return write;
}

type Props = {
  x: number;
  y: number;
  move: Move;
  field: MoveInlineField;
  onSave: (move: Move, patch: Partial<MoveWrite>) => Promise<void>;
  onClose: () => void;
};

export function MoveInlineEdit({ x, y, move, field, onSave, onClose }: Props) {
  const [type, setType] = useState(move.type);
  const [category, setCategory] = useState<Move["category"]>(move.category);
  const [num, setNum] = useState<number | "">(move[fieldKey(field)] ?? "");
  const [target, setTarget] = useState(move.target || "selected");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (saving) return;
    let patch: Partial<MoveWrite>;
    if (field === "type") patch = { type };
    else if (field === "category") patch = { category };
    else if (field === "target") patch = { target };
    else patch = { [field]: num === "" ? null : num };
    setSaving(true);
    setError(null);
    try {
      await onSave(move, patch);
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Save failed");
      setSaving(false);
    }
  }

  return (
    <>
      <div className="dex-edit__backdrop" onMouseDown={onClose} />
      <form
        className="dex-edit"
        data-wide={field === "target" || undefined}
        role="menu"
        aria-label={`Edit ${MOVE_INLINE_LABEL[field]} for ${move.name}`}
        style={{ left: x, top: y }}
        onKeyDown={(e) => e.key === "Escape" && onClose()}
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <div className="dex-edit__head">
          <span className="dex-edit__title">{MOVE_INLINE_LABEL[field]}</span>
          <span className="dex-edit__name">{move.name}</span>
        </div>

        {field === "type" && (
          <TypeSelect id="move-edit-type" label="Type" value={type} onChange={setType} variant="code" />
        )}

        {field === "category" && (
          <CategorySelect
            id="move-edit-category"
            label="Category"
            value={category}
            onChange={(v) => setCategory(v as Move["category"])}
          />
        )}

        {(field === "power" || field === "accuracy" || field === "pp") && (
          <input
            className="dex-edit__input mono"
            type="number"
            inputMode="numeric"
            min={0}
            max={field === "accuracy" ? 100 : 999}
            placeholder="blank = —"
            autoFocus
            value={num}
            onChange={(e) => setNum(e.target.value === "" ? "" : Number(e.target.value))}
          />
        )}

        {field === "target" && (
          <TargetGridField id="move-edit-target" value={target} onChange={setTarget} />
        )}

        {error && <p className="dex-edit__error">{error}</p>}

        <div className="dex-edit__actions">
          <button type="button" className="dex-edit__btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="dex-edit__btn dex-edit__btn--primary" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </>
  );
}

/** The numeric Move key an inline field reads its seed from (type-narrowing
    helper so `move[...]` stays typed for the three number fields). */
function fieldKey(field: MoveInlineField): "power" | "accuracy" | "pp" {
  return field === "power" || field === "accuracy" || field === "pp" ? field : "power";
}
