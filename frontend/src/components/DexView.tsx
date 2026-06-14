import type { DexEntry } from "../types";
import type { ResourceState } from "../hooks/useResource";
import type { DexLayout } from "../hooks/useUrlState";
import type { ColumnKey } from "../lib/dexColumns";
import type { FilterEntry } from "../lib/dexFilters";
import type { SortKey } from "../lib/dexSort";
import { DexGrid } from "./DexGrid";
import { DexTable } from "./DexTable";
import { DexControls, type DexViewPatch } from "./filters/DexControls";
import { ErrorView, EmptyView, GridSkeleton } from "./StatusView";

type Props = {
  resource: ResourceState<DexEntry[]>;
  entries: DexEntry[];
  editedOnly: boolean;
  selected: string | null;
  layout: DexLayout;
  filter: FilterEntry[];
  sort: SortKey[];
  hidden: ColumnKey[];
  onChange: (patch: DexViewPatch) => void;
  onOpen: (chrookedId: string) => void;
};

/** The dex screen: resolves load/error, renders the control stack above a
    scrollable view area, then hands the filtered entries to the sprite grid or
    the dense table per the layout. Controls stay visible on a filtered-empty
    result so the user can always loosen or reset the view. */
export function DexView({
  resource,
  entries,
  editedOnly,
  selected,
  layout,
  filter,
  sort,
  hidden,
  onChange,
  onOpen,
}: Props) {
  if (resource.error !== null) {
    return <ErrorView message={resource.error} status={resource.status} />;
  }
  if (resource.isLoading) {
    return <GridSkeleton />;
  }

  const hasFilter = filter.length > 0;
  return (
    <div className="dex-screen">
      <DexControls
        filter={filter}
        sort={sort}
        hidden={hidden}
        layout={layout}
        onChange={onChange}
      />
      <div className="dex-screen__view">
        {entries.length === 0 ? (
          <EmptyView
            message={
              hasFilter
                ? "No species match this filter."
                : editedOnly
                  ? "No species edited by the Ruleset match this view."
                  : "No species match this search."
            }
          />
        ) : layout === "table" ? (
          <DexTable
            entries={entries}
            selected={selected}
            sort={sort}
            hidden={hidden}
            onSort={(next) => onChange({ sort: next })}
            onOpen={onOpen}
          />
        ) : (
          <DexGrid entries={entries} selected={selected} onOpen={onOpen} />
        )}
      </div>
    </div>
  );
}
