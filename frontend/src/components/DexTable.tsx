import { useCallback, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { CanonicalMethod, DexEntry, TargetNamespace } from "../types";
import {
  ADVANCED_ID,
  requiredValueMissing,
  seedMethodForm,
  serializeMethod,
} from "./editors/evolutionMethod";
import { bst, dexLabel, isEdited, STAT_LABEL, TYPES, type StatKey } from "../lib/format";
import type { InlineEdit, AbilitySlot } from "../lib/inlineEdit";
import { COLUMNS, type Column, type ColumnKey } from "../lib/dexColumns";
import type { SortKey } from "../lib/dexSort";
import { TypeChip } from "./TypeChip";
import { EditedLed } from "./EditedLed";
import { DexSprite } from "./DexSprite";
import "./dex-table.css";

/** Which cell a right-click targeted — the field the inline menu will edit. */
type EditField =
  | { kind: "stat"; key: StatKey }
  | { kind: "types" }
  | { kind: "ability" }
  | { kind: "evolution" };

type Props = {
  entries: DexEntry[];
  selected: string | null;
  sort: SortKey[];
  hidden: ColumnKey[];
  onSort: (sort: SortKey[]) => void;
  onOpen: (chrookedId: string) => void;
  backdropTargetId?: string | null;
  /** Known ability names, for the inline ability combobox. */
  abilityOptions?: readonly string[];
  /** Known species names, for the inline evolution pre-evo combobox. */
  speciesOptions?: readonly string[];
  /** Canonical evolution methods, for the inline evolution method select. */
  evolutionMethods?: readonly CanonicalMethod[];
  /** When provided, right-clicking a stat/types/abilities cell opens an inline
      edit menu that saves one Override field to the chosen scope. */
  onInlineEdit?: (entry: DexEntry, edit: InlineEdit, scope?: string) => Promise<void>;
  /** Backdrop's Override namespace — when set, the menu offers a scope choice
      (this Target vs Canon Ruleset), defaulting to the Target. */
  inlineScopeTarget?: TargetNamespace | null;
};

const ROW_HEIGHT = 38;
const MAX_SORT_KEYS = 3;

/** Grid track per column, matching the historical static template. The visible
    set joins these into `--dexcols`, so hiding a column re-flows the rest. */
const WIDTH: Record<ColumnKey, string> = {
  led: "1.5rem",
  dex: "3.5rem",
  name: "minmax(11rem, 1.4fr)",
  types: "5.5rem",
  hp: "3rem",
  atk: "3rem",
  def: "3rem",
  spa: "3rem",
  spd: "3rem",
  spe: "3rem",
  bst: "3.5rem",
  abilities: "minmax(12rem, 1.6fr)",
  evolution: "minmax(9rem, 1.1fr)",
};

/**
 * The dense table view of the Canon dex. Columns are dynamic (the visible set
 * comes from COLUMNS minus `hidden`), and data-column headers sort on click
 * (shift-click appends a secondary key, click again flips direction). Mono data,
 * an overridden value keyed amber, the row's edited LED carrying the signal.
 * Rows are windowed; the header stays pinned.
 */
export function DexTable({ entries, selected, sort, hidden, onSort, onOpen, backdropTargetId, abilityOptions, speciesOptions, evolutionMethods, onInlineEdit, inlineScopeTarget }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Right-click inline edit menu. Null when closed; carries the cursor position,
  // the species, and which field the targeted cell maps to.
  const [menu, setMenu] = useState<{ x: number; y: number; entry: DexEntry; field: EditField } | null>(null);
  const openEdit = useCallback(
    (e: React.MouseEvent, entry: DexEntry, field: EditField) => {
      if (!onInlineEdit) return;
      e.preventDefault();
      e.stopPropagation();
      setMenu({ x: Math.min(e.clientX, window.innerWidth - 240), y: Math.min(e.clientY, window.innerHeight - 200), entry, field });
    },
    [onInlineEdit],
  );
  const rowVirtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  const hiddenSet = new Set(hidden);
  const visible = COLUMNS.filter((c) => !hiddenSet.has(c.key));
  const cols = visible.map((c) => WIDTH[c.key]).join(" ");

  const handleSort = useCallback(
    (field: ColumnKey, append: boolean) => {
      const existing = sort.find((s) => s.field === field);
      const flip = (d: "asc" | "desc"): "asc" | "desc" => (d === "asc" ? "desc" : "asc");
      if (append) {
        if (existing) {
          onSort(sort.map((s) => (s.field === field ? { ...s, direction: flip(s.direction) } : s)));
        } else if (sort.length < MAX_SORT_KEYS) {
          onSort([...sort, { field, direction: "asc" }]);
        }
      } else if (existing && sort.length === 1) {
        onSort([{ field, direction: flip(existing.direction) }]);
      } else {
        onSort([{ field, direction: "asc" }]);
      }
    },
    [sort, onSort],
  );

  return (
    <div className="dex-table" ref={scrollRef} id="dex-table">
      <div
        className="dex-table__inner"
        role="table"
        aria-label={`Canon dex — ${entries.length} species`}
        aria-rowcount={entries.length + 1}
        style={{ ["--dexcols"]: cols } as React.CSSProperties}
      >
        <div className="dex-table__head" role="row" aria-rowindex={1}>
          {visible.map((col) => (
            <HeaderCell
              key={col.key}
              col={col}
              sortIndex={sort.findIndex((s) => s.field === col.key)}
              direction={sort.find((s) => s.field === col.key)?.direction}
              multi={sort.length > 1}
              onSort={handleSort}
            />
          ))}
        </div>

        <div
          className="dex-table__body"
          style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
        >
          {rowVirtualizer.getVirtualItems().map((vrow) => {
            const entry = entries[vrow.index];
            return (
              <DexRow
                key={entry.chrooked_id}
                entry={entry}
                rowIndex={vrow.index + 2}
                isSelected={entry.chrooked_id === selected}
                columns={visible}
                top={vrow.start}
                onOpen={onOpen}
                onEdit={onInlineEdit ? openEdit : undefined}
                backdropTargetId={backdropTargetId}
              />
            );
          })}
        </div>
      </div>

      {menu && onInlineEdit && (
        <InlineEditMenu
          key={`${menu.entry.chrooked_id}:${menu.field.kind}:${menu.field.kind === "stat" ? menu.field.key : ""}`}
          x={menu.x}
          y={menu.y}
          entry={menu.entry}
          field={menu.field}
          abilityOptions={abilityOptions ?? []}
          speciesOptions={speciesOptions ?? []}
          evolutionMethods={evolutionMethods ?? []}
          scopeTarget={inlineScopeTarget ?? null}
          onSave={onInlineEdit}
          onClose={() => setMenu(null)}
        />
      )}
    </div>
  );
}

const HEADER_CLASS: Record<ColumnKey, string> = {
  led: "dex-table__led",
  dex: "dex-table__num",
  name: "dex-table__name",
  types: "dex-table__types",
  hp: "dex-table__stat mono",
  atk: "dex-table__stat mono",
  def: "dex-table__stat mono",
  spa: "dex-table__stat mono",
  spd: "dex-table__stat mono",
  spe: "dex-table__stat mono",
  bst: "dex-table__stat mono",
  abilities: "dex-table__abil",
  evolution: "dex-table__evo",
};

type HeaderProps = {
  col: (typeof COLUMNS)[number];
  sortIndex: number;
  direction: "asc" | "desc" | undefined;
  multi: boolean;
  onSort: (field: ColumnKey, append: boolean) => void;
};

function HeaderCell({ col, sortIndex, direction, multi, onSort }: HeaderProps) {
  const ariaSort = direction === "asc" ? "ascending" : direction === "desc" ? "descending" : undefined;
  const label = col.key === "led" ? <span className="sr-only">Edited</span> : col.label;

  if (!col.sortable) {
    return (
      <span className={`dex-table__h ${HEADER_CLASS[col.key]}`} role="columnheader">
        {label}
      </span>
    );
  }

  return (
    <span
      className={`dex-table__h ${HEADER_CLASS[col.key]}`}
      role="columnheader"
      aria-sort={ariaSort}
    >
      <button
        type="button"
        className="dex-table__sortbtn"
        data-active={direction !== undefined || undefined}
        onClick={(e) => onSort(col.key, e.shiftKey)}
        title="Click to sort · Shift-click to add a secondary sort"
      >
        {col.label}
        {direction !== undefined && (
          <span className="dex-table__sortmark" aria-hidden="true">
            {direction === "asc" ? "▲" : "▼"}
            {multi && <span className="dex-table__sortord">{sortIndex + 1}</span>}
          </span>
        )}
      </button>
    </span>
  );
}

type EditOpener = (e: React.MouseEvent, entry: DexEntry, field: EditField) => void;

type RowProps = {
  entry: DexEntry;
  rowIndex: number;
  isSelected: boolean;
  columns: Column[];
  top: number;
  onOpen: (id: string) => void;
  onEdit?: EditOpener;
  backdropTargetId?: string | null;
};

function DexRow({ entry, rowIndex, isSelected, columns, top, onOpen, onEdit, backdropTargetId }: RowProps) {
  const edited = isEdited(entry);
  const open = useCallback(() => onOpen(entry.chrooked_id), [onOpen, entry.chrooked_id]);

  return (
    <div
      className="dex-table__row"
      role="row"
      aria-rowindex={rowIndex}
      data-edited={edited || undefined}
      data-selected={isSelected || undefined}
      style={{ transform: `translateY(${top}px)` }}
      onClick={open}
    >
      {/* Cells iterate the SAME visible-column list the header uses, so header
          and data can never drift out of alignment. */}
      {columns.map((col) => renderCell(col, entry, edited, open, backdropTargetId, onEdit))}
    </div>
  );
}

/** One table cell for a column. Bespoke per column kind, but always emitted from
    the shared visible-column iteration so it lines up with the header. */
function renderCell(
  col: Column,
  entry: DexEntry,
  edited: boolean,
  open: () => void,
  backdropTargetId?: string | null,
  onEdit?: EditOpener,
) {
  switch (col.key) {
    case "led":
      return (
        <span key="led" className="dex-table__c dex-table__led" role="cell">
          <EditedLed on={edited} />
        </span>
      );
    case "dex":
      return (
        <span key="dex" className="dex-table__c dex-table__num mono" role="cell">
          {dexLabel(entry.dex).replace("№ ", "")}
        </span>
      );
    case "name":
      return (
        <span key="name" className="dex-table__c dex-table__name" role="cell">
          <DexSprite
            chrookedId={entry.chrooked_id}
            dex={entry.dex}
            name=""
            backdropTargetId={backdropTargetId}
            size={28}
          />
          <button
            type="button"
            className="dex-table__namebtn"
            onClick={(e) => {
              e.stopPropagation();
              open();
            }}
          >
            {entry.name}
          </button>
        </span>
      );
    case "types":
      return (
        <span
          key="types"
          className="dex-table__c dex-table__types"
          role="cell"
          data-editable={onEdit ? true : undefined}
          onContextMenu={onEdit ? (e) => onEdit(e, entry, { kind: "types" }) : undefined}
        >
          {entry.types.map((t) => (
            <TypeChip key={t} type={t} variant="code" />
          ))}
        </span>
      );
    case "bst":
      return (
        <span key="bst" className="dex-table__c dex-table__stat dex-table__bst mono" role="cell">
          {bst(entry.stats) ?? "—"}
        </span>
      );
    case "abilities":
      return (
        <span
          key="abilities"
          className="dex-table__c dex-table__abil"
          role="cell"
          data-editable={onEdit ? true : undefined}
          onContextMenu={onEdit ? (e) => onEdit(e, entry, { kind: "ability" }) : undefined}
        >
          {abilityList(entry)}
        </span>
      );
    case "evolution":
      return (
        <span
          key="evolution"
          className="dex-table__c dex-table__evo"
          role="cell"
          data-changed={entry.overridden_fields.includes("evolution") || undefined}
          data-editable={onEdit ? true : undefined}
          onContextMenu={onEdit ? (e) => onEdit(e, entry, { kind: "evolution" }) : undefined}
        >
          {evolutionLabel(entry) ?? <span className="dex-table__faint">—</span>}
        </span>
      );
    default: {
      // one of the six stat columns
      const changed = (entry.base.stats ?? {})[col.key] !== undefined;
      return (
        <span
          key={col.key}
          className="dex-table__c dex-table__stat mono"
          role="cell"
          data-changed={changed || undefined}
          data-editable={onEdit ? true : undefined}
          onContextMenu={onEdit ? (e) => onEdit(e, entry, { kind: "stat", key: col.key as StatKey }) : undefined}
        >
          {entry.stats[col.key] ?? "—"}
        </span>
      );
    }
  }
}

const ABILITY_SLOTS: readonly AbilitySlot[] = ["primary", "secondary", "hidden"];

type MenuProps = {
  x: number;
  y: number;
  entry: DexEntry;
  field: EditField;
  abilityOptions: readonly string[];
  speciesOptions: readonly string[];
  evolutionMethods: readonly CanonicalMethod[];
  scopeTarget: TargetNamespace | null;
  onSave: (entry: DexEntry, edit: InlineEdit, scope?: string) => Promise<void>;
  onClose: () => void;
};

/** The right-click popover. Seeds from the cell's current merged value, edits one
    field, and hands an {@link InlineEdit} to onSave (which builds the
    overrides-only payload and PUTs it). On a Target backdrop a scope select
    routes the write to that Target's namespace (default) or the Canon Ruleset —
    the same contract as the modal editor's toggle. Closes on save, Escape, or
    backdrop. */
function InlineEditMenu({ x, y, entry, field, abilityOptions, speciesOptions, evolutionMethods, scopeTarget, onSave, onClose }: MenuProps) {
  const [statValue, setStatValue] = useState<number | "">(
    field.kind === "stat" ? entry.stats[field.key] ?? "" : "",
  );
  const [type1, setType1] = useState(entry.types[0] ?? "");
  const [type2, setType2] = useState(entry.types[1] ?? "");
  const [slot, setSlot] = useState<AbilitySlot>("primary");
  const [ability, setAbility] = useState(entry.abilities.primary ?? "");
  // Evolution: pre-evo name + the same MethodForm the modal editor uses.
  const [evoFrom, setEvoFrom] = useState(entry.evolution?.from_name ?? entry.evolution?.from ?? "");
  const [evoForm, setEvoForm] = useState(() => seedMethodForm(entry.evolution, evolutionMethods));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Backdrop open on purpose → default the write to that Target's namespace
  // (mirrors SpeciesEditor's scopeToTarget default).
  const [scopeToTarget, setScopeToTarget] = useState(true);
  const scope = scopeTarget && scopeToTarget ? `target:${scopeTarget.slug}` : "base";

  // Switching ability slot reseeds the name field to that slot's current value.
  const pickSlot = (next: AbilitySlot) => {
    setSlot(next);
    setAbility(entry.abilities[next] ?? "");
  };

  async function submit() {
    if (saving) return;
    let edit: InlineEdit;
    if (field.kind === "stat") {
      if (statValue === "") return;
      edit = { kind: "stat", key: field.key, value: statValue };
    } else if (field.kind === "types") {
      edit = { kind: "types", type1, type2 };
    } else if (field.kind === "evolution") {
      if (evoFrom.trim() !== "" && requiredValueMissing(evoForm, evolutionMethods)) {
        setError("Set a value for the evolution method.");
        return;
      }
      edit = { kind: "evolution", from: evoFrom, method: serializeMethod(evoForm, evolutionMethods) };
    } else {
      edit = { kind: "ability", slot, name: ability };
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(entry, edit, scope);
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Save failed");
      setSaving(false);
    }
  }

  const title =
    field.kind === "stat" ? STAT_LABEL[field.key]
    : field.kind === "types" ? "Types"
    : field.kind === "evolution" ? "Evolution"
    : "Abilities";

  return (
    <>
      <div className="dex-edit__backdrop" onMouseDown={onClose} />
      <form
        className="dex-edit"
        role="menu"
        aria-label={`Edit ${title} for ${entry.name}`}
        style={{ left: x, top: y }}
        onKeyDown={(e) => e.key === "Escape" && onClose()}
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <div className="dex-edit__head">
          <span className="dex-edit__title">{title}</span>
          <span className="dex-edit__name">{entry.name}</span>
        </div>

        {field.kind === "stat" && (
          <input
            className="dex-edit__input mono"
            type="number"
            inputMode="numeric"
            min={0}
            max={255}
            autoFocus
            value={statValue}
            onChange={(e) => setStatValue(e.target.value === "" ? "" : Math.max(0, Math.min(255, Number(e.target.value))))}
          />
        )}

        {field.kind === "types" && (
          <div className="dex-edit__row">
            <select className="dex-edit__select" autoFocus value={type1} onChange={(e) => setType1(e.target.value)}>
              {TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <select className="dex-edit__select" value={type2} onChange={(e) => setType2(e.target.value)}>
              <option value="">— none —</option>
              {TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        )}

        {field.kind === "ability" && (
          <div className="dex-edit__row">
            <select className="dex-edit__select" value={slot} onChange={(e) => pickSlot(e.target.value as AbilitySlot)}>
              {ABILITY_SLOTS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <input
              className="dex-edit__input"
              type="text"
              list="dex-edit-abilities"
              autoComplete="off"
              placeholder="blank = base"
              value={ability}
              onChange={(e) => setAbility(e.target.value)}
            />
            <datalist id="dex-edit-abilities">
              {abilityOptions.map((a) => (
                <option key={a} value={a} />
              ))}
            </datalist>
          </div>
        )}

        {field.kind === "evolution" && (
          <>
            <div className="dex-edit__row">
              <input
                className="dex-edit__input"
                type="text"
                list="dex-edit-species"
                autoComplete="off"
                autoFocus
                placeholder="pre-evo; blank = none"
                value={evoFrom}
                onChange={(e) => setEvoFrom(e.target.value)}
              />
              <datalist id="dex-edit-species">
                {speciesOptions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>
            <div className="dex-edit__row">
              <select
                className="dex-edit__select"
                aria-label="Evolution method"
                value={evoForm.id}
                onChange={(e) => setEvoForm({ ...evoForm, id: e.target.value, value: "" })}
              >
                {evolutionMethods.map((m) => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
                <option value={ADVANCED_ID}>Advanced (raw token)</option>
              </select>
              {evoForm.id === ADVANCED_ID ? (
                <>
                  <input
                    className="dex-edit__input mono"
                    type="text"
                    placeholder="EVO_TOKEN"
                    value={evoForm.rawToken}
                    onChange={(e) => setEvoForm({ ...evoForm, rawToken: e.target.value })}
                  />
                  <input
                    className="dex-edit__input mono"
                    type="text"
                    placeholder="param"
                    value={evoForm.rawParam}
                    onChange={(e) => setEvoForm({ ...evoForm, rawParam: e.target.value })}
                  />
                </>
              ) : (
                evoNeedsValue(evoForm.id, evolutionMethods) && (
                  <input
                    className="dex-edit__input"
                    type="text"
                    placeholder="value"
                    value={evoForm.value}
                    onChange={(e) => setEvoForm({ ...evoForm, value: e.target.value })}
                  />
                )
              )}
            </div>
          </>
        )}

        {scopeTarget && (
          <select
            id="dex-edit-scope"
            className="dex-edit__select"
            aria-label="Edit scope"
            value={scopeToTarget ? "target" : "base"}
            onChange={(e) => setScopeToTarget(e.target.value === "target")}
          >
            <option value="target">{scopeTarget.label} only</option>
            <option value="base">Canon Ruleset</option>
          </select>
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

/** True when a canonical method id takes a value (level/item/move/map). */
function evoNeedsValue(id: string, methods: readonly CanonicalMethod[]): boolean {
  const kind = methods.find((m) => m.id === id)?.value_kind;
  return kind === "level" || kind === "item" || kind === "move" || kind === "map";
}

/** "Goldeen · Level 30" — pre-evo plus a compact method label. Handles both
    method shapes (backdrop display string vs Override dict). Null = base mon. */
function evolutionLabel(entry: DexEntry): string | null {
  const evo = entry.evolution;
  if (!evo || !evo.from) return null;
  const from = evo.from_name ?? evo.from;
  const m = evo.method;
  let label: string;
  if (typeof m === "string") label = m;
  else if ("level" in m) label = `Level ${m.level}`;
  else if ("item" in m) label = String(m.item);
  else if ("method" in m) label = `${m.method}${"param" in m ? ` ${m.param}` : ""}`;
  else label = Object.values(m).map(String).join(" ");
  return label ? `${from} · ${label}` : from;
}

/** Abilities as "primary · secondary · hidden", dim, with the hidden one marked. */
function abilityList(entry: DexEntry) {
  const { primary, secondary, hidden } = entry.abilities;
  const changed = entry.base.abilities ?? null;
  const slots: { value: string | null; slot: "primary" | "secondary" | "hidden" }[] = [
    { value: primary, slot: "primary" },
    { value: secondary, slot: "secondary" },
    { value: hidden, slot: "hidden" },
  ];
  const shown = slots.filter((s) => s.value);
  if (shown.length === 0) return <span className="dex-table__faint">—</span>;
  return (
    <span className="dex-table__abils">
      {shown.map((s, i) => (
        <span
          key={s.slot}
          className="dex-table__abil-item"
          data-hidden={s.slot === "hidden" || undefined}
          data-changed={changed !== null && changed[s.slot] !== undefined ? true : undefined}
        >
          {i > 0 && <span className="dex-table__sep" aria-hidden="true"> · </span>}
          {s.value}
          {s.slot === "hidden" && <span className="sr-only"> (hidden ability)</span>}
        </span>
      ))}
    </span>
  );
}
