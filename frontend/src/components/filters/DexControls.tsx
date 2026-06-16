import type { ColumnKey } from "../../lib/dexColumns";
import { COLUMNS } from "../../lib/dexColumns";
import type { FilterEntry } from "../../lib/filterEngine";
import { DEX_REGISTRY } from "../../lib/dexFilters";
import type { SortKey } from "../../lib/dexSort";
import type { DexLayout } from "../../hooks/useUrlState";
import { EntityControls, type EntityViewPatch } from "./EntityControls";
import "./filters.css";

export type DexViewPatch = {
  filter?: FilterEntry[];
  sort?: SortKey[];
  hidden?: ColumnKey[];
};

type Props = {
  filter: FilterEntry[];
  sort: SortKey[];
  hidden: ColumnKey[];
  layout: DexLayout;
  onChange: (patch: DexViewPatch) => void;
};

const SORTABLE = COLUMNS.filter((c) => c.sortable).map((c) => ({
  key: c.key,
  label: c.label,
}));
const TOGGLEABLE = COLUMNS.filter((c) => !c.locked).map((c) => ({
  key: c.key,
  label: c.label,
}));

/**
 * The control stack above the dex, a thin dex binding of the shared
 * EntityControls. The filter builder applies to both views; the sort row and
 * column toggles are table-only (the grid is dex-ordered and column-less).
 * Switching grid→table preserves filters and reveals the rest.
 */
export function DexControls({ filter, sort, hidden, layout, onChange }: Props) {
  const isTable = layout === "table";

  // The generic patch carries `string` keys; narrow them back to the dex's
  // ColumnKey before handing the patch up (the codec already validates on read).
  function handleChange(patch: EntityViewPatch) {
    const dexPatch: DexViewPatch = {};
    if (patch.filter !== undefined) dexPatch.filter = patch.filter;
    if (patch.sort !== undefined) dexPatch.sort = patch.sort as SortKey[];
    if (patch.hidden !== undefined) dexPatch.hidden = patch.hidden as ColumnKey[];
    onChange(dexPatch);
  }

  return (
    <EntityControls
      idPrefix="dexc"
      ariaLabel="Dex view controls"
      defs={DEX_REGISTRY.defs}
      sortable={isTable ? SORTABLE : []}
      columns={isTable ? TOGGLEABLE : []}
      filter={filter}
      sort={sort}
      hidden={hidden}
      onChange={handleChange}
    />
  );
}
