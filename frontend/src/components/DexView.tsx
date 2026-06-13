import type { DexEntry } from "../types";
import type { ResourceState } from "../hooks/useResource";
import { DexGrid } from "./DexGrid";
import { ErrorView, EmptyView, GridSkeleton } from "./StatusView";

type Props = {
  resource: ResourceState<DexEntry[]>;
  entries: DexEntry[];
  editedOnly: boolean;
  selected: string | null;
  onOpen: (chrookedId: string) => void;
};

/** The dex screen: resolves the load/error/empty states, then hands the
    filtered entries to the virtualized grid. */
export function DexView({ resource, entries, editedOnly, selected, onOpen }: Props) {
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
  return <DexGrid entries={entries} selected={selected} onOpen={onOpen} />;
}
