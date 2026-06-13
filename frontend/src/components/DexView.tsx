import type { DexEntry } from "../types";
import type { ResourceState } from "../hooks/useResource";
import type { DexLayout } from "../hooks/useUrlState";
import { DexGrid } from "./DexGrid";
import { DexTable } from "./DexTable";
import { ErrorView, EmptyView, GridSkeleton } from "./StatusView";

type Props = {
  resource: ResourceState<DexEntry[]>;
  entries: DexEntry[];
  editedOnly: boolean;
  selected: string | null;
  layout: DexLayout;
  onOpen: (chrookedId: string) => void;
};

/** The dex screen: resolves the load/error/empty states, then hands the
    filtered entries to the sprite grid or the dense table per the layout. */
export function DexView({
  resource,
  entries,
  editedOnly,
  selected,
  layout,
  onOpen,
}: Props) {
  if (resource.error !== null) {
    return <ErrorView message={resource.error} status={resource.status} />;
  }
  if (resource.isLoading) {
    return <GridSkeleton />;
  }
  if (entries.length === 0) {
    return (
      <EmptyView
        message={
          editedOnly
            ? "No species edited by the Ruleset match this view."
            : "No species match this search."
        }
      />
    );
  }
  return layout === "table" ? (
    <DexTable entries={entries} selected={selected} onOpen={onOpen} />
  ) : (
    <DexGrid entries={entries} selected={selected} onOpen={onOpen} />
  );
}
