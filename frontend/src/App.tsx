import { useCallback, useEffect, useMemo, useRef } from "react";
import { api } from "./api";
import { useResource } from "./hooks/useResource";
import { useUrlState } from "./hooks/useUrlState";
import { isEdited } from "./lib/format";
import { onDataChange } from "./lib/dataChange";
import { evalEntries, appendNameFilter } from "./lib/dexFilters";
import { stableMultiSort } from "./lib/dexSort";
import { searchTargetFor, promoteSearchToPill } from "./lib/searchDispatch";
import type { DexEntry, KindKey, Move } from "./types";
import { DeviceFrame } from "./components/DeviceFrame";
import { DexView } from "./components/DexView";
import type { DexViewPatch } from "./components/filters/DexControls";
import { DetailLedger } from "./components/DetailLedger";
import { MovesTab } from "./components/tabs/MovesTab";
import { AbilitiesTab } from "./components/tabs/AbilitiesTab";
import { TypeChartTab } from "./components/tabs/TypeChartTab";
import { BehaviorsTab } from "./components/tabs/BehaviorsTab";
import { TargetsTab } from "./components/tabs/TargetsTab";
import { BackdropChip } from "./components/targets/BackdropChip";

/**
 * The Canon dex app shell. Owns the dex fetch, the URL-persisted view state, and
 * the keyboard shortcuts; delegates each kind to its own screen. The detail
 * ledger overlays the dex when a species is open.
 */
export default function App() {
  const [view, update] = useUrlState();
  // The dex fetch swaps to a Target's backdrop (target ⊕ Ruleset) when one is
  // set; otherwise it reads the base ⊕ Ruleset canon. Memoized by backdrop id so
  // useResource sees a stable fetcher and refetches only when the backdrop flips.
  const dexFetcher = useMemo(
    () => (view.backdrop ? api.targetDex(view.backdrop) : api.dex),
    [view.backdrop],
  );
  const dex = useResource<DexEntry[]>(dexFetcher);
  const moves = useResource<Move[]>(api.moves);
  const reloadDex = dex.reload;
  const searchRef = useRef<HTMLInputElement>(null);

  // The dex resource is mounted for the whole app, so a species write made from
  // another screen (e.g. ability/move distribution on its tab) would leave the
  // dex page stale. Refetch whenever a species mutation signals a data change.
  useEffect(() => onDataChange(() => reloadDex()), [reloadDex]);

  const all = useMemo(() => dex.data ?? [], [dex.data]);
  const editedCount = useMemo(() => all.filter(isEdited).length, [all]);

  const moveOptions = useMemo(() => {
    const names = new Set<string>();
    for (const m of moves.data ?? []) names.add(m.name);
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [moves.data]);

  const speciesOptions = useMemo(
    () => all.map((e) => e.name).sort((a, b) => a.localeCompare(b)),
    [all],
  );

  // Distinct ability names across the merged dex (base + overrides) — the
  // suggestion set for the species editor's ability comboboxes.
  const abilityOptions = useMemo(() => {
    const names = new Set<string>();
    for (const entry of all) {
      for (const slot of [
        entry.abilities.primary,
        entry.abilities.secondary,
        entry.abilities.hidden,
      ]) {
        if (slot) names.add(slot);
      }
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [all]);

  // Row predicates: edited-only, then the rail search, then the boolean filter
  // builder. All three apply to both grid and table. `view.filter`/`view.sort`
  // are safe memo deps: useUrlState caches the whole ViewState by the raw query
  // string, so these arrays keep a stable reference until the URL changes.
  const filtered = useMemo(() => {
    let list = all;
    if (view.editedOnly) {
      list = list.filter(isEdited);
    }
    const query = view.query.trim().toLowerCase();
    if (query) {
      list = list.filter(
        (entry) =>
          entry.name.toLowerCase().includes(query) ||
          String(entry.dex ?? "").includes(query),
      );
    }
    if (view.filter.length) {
      list = list.filter((entry) => evalEntries(entry, view.filter));
    }
    return list;
  }, [all, view.editedOnly, view.query, view.filter]);

  // The table additionally sorts by the multi-key sort spec; the grid stays in
  // dex order. Only the visible view's list is consumed, so this is cheap.
  const tableRows = useMemo(
    () => stableMultiSort(filtered, view.sort),
    [filtered, view.sort],
  );
  const dexEntries = view.layout === "table" ? tableRows : filtered;

  const isDex = view.kind === "dex";
  const selectedEntry =
    isDex && view.selected !== null
      ? all.find((entry) => entry.chrooked_id === view.selected) ?? null
      : null;

  // Stable so memo(DexCell) holds across the 1451-cell grid (`update` is stable).
  const handleOpen = useCallback(
    (id: string) => update({ selected: id }),
    [update],
  );
  const handleClose = useCallback(() => update({ selected: null }), [update]);

  // From a species profile cross-link (#28): jump to the entity's page and open
  // its read-only detail. Types route to the Type Chart and open the breakdown
  // via the shared `q` (the #18 ac10 selection path); moves/abilities route to
  // their tab and open the DetailSidebar via `id` (the tab resolves the key
  // against both chrooked_id and display name). The dex detail closes on the way
  // out (selected: null) so the destination tab is unobstructed.
  const handleNavigate = useCallback(
    (kind: KindKey, key: string) => {
      if (kind === "type-chart") {
        update({ kind, query: key, selected: null });
        return;
      }
      update({ kind, selected: key, query: "" });
    },
    [update],
  );

  // From the Targets panel: show the dex on this fork's backdrop and jump to it.
  const handleViewBackdrop = useCallback(
    (targetId: string) =>
      update({ kind: "dex", backdrop: targetId, selected: null }),
    [update],
  );
  const handleClearBackdrop = useCallback(
    () => update({ backdrop: null }),
    [update],
  );

  // Enter in the rail search promotes the term to a composable Name filter pill
  // on the ACTIVE entity, then clears the box (ac9). The dex writes its own
  // `filter` param via useUrlState; moves/abilities write their namespaced filter
  // param via the search dispatch. No-op (search kept) when blank, at the pill
  // cap, or a duplicate — appendNameFilter signals that by returning the same
  // array reference.
  const handleSearchEnter = useCallback(() => {
    // Type Chart has no filter pills — its "search target" is selecting a type,
    // which TypeChartTab does by reacting to view.query live. Enter is a no-op at
    // the App level there (the match is already open); we leave the box as-is.
    if (view.kind === "type-chart") {
      return;
    }
    const target = searchTargetFor(view.kind);
    if (target === null) {
      const next = appendNameFilter(view.filter, view.query, crypto.randomUUID());
      if (next !== view.filter) {
        update({ filter: next, query: "" });
      }
      return;
    }
    if (promoteSearchToPill(target, view.query, crypto.randomUUID())) {
      update({ query: "" });
    }
  }, [view.kind, view.filter, view.query, update]);

  // The rail search is the single search for the dex, Moves, Abilities (ac9), and
  // the Type Chart (ac10): live name-filtering / type-selection lives in each tab,
  // Enter promotes a Name pill (dex/moves/abilities) or is a no-op (type-chart,
  // which selects live). The `/` shortcut focuses it on every page. The same four
  // pages honor the shared `view.editedOnly` flag (ac12) — the rail "Edited only"
  // button and the `E` shortcut both drive it.
  const isSearchable =
    isDex ||
    view.kind === "moves" ||
    view.kind === "abilities" ||
    view.kind === "type-chart";
  const isEditedFilterable = isSearchable;

  useGlobalKeys({
    onSearch: () => searchRef.current?.focus(),
    onToggleEdited: () =>
      isEditedFilterable && update({ editedOnly: !view.editedOnly }),
    onEscape: () => selectedEntry !== null && update({ selected: null }),
    enabled: isEditedFilterable,
    hasSelection: selectedEntry !== null,
  });

  return (
    <DeviceFrame
      kind={view.kind}
      onKind={(kind) => update({ kind, selected: null })}
      query={view.query}
      onQuery={(query) => update({ query })}
      searchable={isSearchable}
      editedOnly={view.editedOnly}
      onEditedOnly={(editedOnly) => update({ editedOnly })}
      onSearchEnter={handleSearchEnter}
      layout={view.layout}
      onLayout={(layout) => update({ layout })}
      searchRef={searchRef}
      readout={
        <>
          <Readout kind={view.kind} total={all.length} edited={editedCount} shown={filtered.length} />
          {/* The backdrop chip rides along on the dex, abilities, moves, and
              type-chart tabs — each swaps its fetcher to the Target's fork ⊕
              Ruleset when set. */}
          {(isDex ||
            view.kind === "abilities" ||
            view.kind === "moves" ||
            view.kind === "type-chart") &&
            view.backdrop !== null && (
              <BackdropChip
                targetId={view.backdrop}
                onClear={handleClearBackdrop}
              />
            )}
        </>
      }
    >
      {/* Background is inert while the detail dialog is open: it can't be
          tabbed into and is hidden from assistive tech (focus trap). `inert`
          is spread as a raw attribute for React 18 (typed in React 19). */}
      <div
        className="device__layer"
        {...(selectedEntry !== null
          ? ({ inert: "" } as Record<string, string>)
          : {})}
      >
        <KindScreen
          kind={view.kind}
          dexResource={dex}
          entries={dexEntries}
          editedOnly={view.editedOnly}
          selected={view.selected}
          layout={view.layout}
          filter={view.filter}
          sort={view.sort}
          hidden={view.hidden}
          onChange={update}
          onOpen={handleOpen}
          onViewBackdrop={handleViewBackdrop}
        />
      </div>
      {selectedEntry !== null && (
        <DetailLedger
          entry={selectedEntry}
          onClose={handleClose}
          onSaved={dex.reload}
          onNavigate={handleNavigate}
          abilityOptions={abilityOptions}
          moveOptions={moveOptions}
          speciesOptions={speciesOptions}
        />
      )}
    </DeviceFrame>
  );
}

type ViewSnapshot = ReturnType<typeof useUrlState>[0];

type KindScreenProps = {
  kind: ViewSnapshot["kind"];
  dexResource: ReturnType<typeof useResource<DexEntry[]>>;
  entries: DexEntry[];
  editedOnly: boolean;
  selected: string | null;
  layout: ViewSnapshot["layout"];
  filter: ViewSnapshot["filter"];
  sort: ViewSnapshot["sort"];
  hidden: ViewSnapshot["hidden"];
  onChange: (patch: DexViewPatch) => void;
  onOpen: (id: string) => void;
  onViewBackdrop: (targetId: string) => void;
};

function KindScreen({
  kind,
  dexResource,
  entries,
  editedOnly,
  selected,
  layout,
  filter,
  sort,
  hidden,
  onChange,
  onOpen,
  onViewBackdrop,
}: KindScreenProps) {
  switch (kind) {
    case "moves":
      return <MovesTab />;
    case "abilities":
      return <AbilitiesTab />;
    case "type-chart":
      return <TypeChartTab />;
    case "behaviors":
      return <BehaviorsTab />;
    case "targets":
      return <TargetsTab onViewBackdrop={onViewBackdrop} />;
    default:
      return (
        <DexView
          resource={dexResource}
          entries={entries}
          editedOnly={editedOnly}
          selected={selected}
          layout={layout}
          filter={filter}
          sort={sort}
          hidden={hidden}
          onChange={onChange}
          onOpen={onOpen}
        />
      );
  }
}

function Readout({
  kind,
  total,
  edited,
  shown,
}: {
  kind: string;
  total: number;
  edited: number;
  shown: number;
}) {
  if (kind === "targets") {
    return <span>targets · preview &amp; apply</span>;
  }
  if (kind !== "dex") {
    return <span>{kind.replace("-", " ")} · read-only</span>;
  }
  return (
    <span>
      {total} species ·{" "}
      <span style={{ color: "var(--edited)" }}>
        {edited} edited<span className="sr-only"> by the Ruleset</span>
      </span>
      {shown !== total && ` · ${shown} shown`}
    </span>
  );
}

type KeyHandlers = {
  onSearch: () => void;
  onToggleEdited: () => void;
  onEscape: () => void;
  enabled: boolean;
  hasSelection: boolean;
};

/** Global keyboard shortcuts: `/` focuses search, `e` toggles the edited filter,
    Escape closes the detail. Shortcuts ignore keystrokes inside form fields. */
function useGlobalKeys(handlers: KeyHandlers): void {
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const { onSearch, onToggleEdited, onEscape, enabled, hasSelection } = ref.current;
      // Escape closes the detail regardless of `enabled` — the dialog can be
      // open over any kind, and Escape should always dismiss it first.
      if (event.key === "Escape" && hasSelection) {
        onEscape();
        return;
      }
      const target = event.target as HTMLElement | null;
      const inField =
        target !== null &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (inField || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      if (event.key === "/") {
        event.preventDefault();
        onSearch();
      } else if ((event.key === "e" || event.key === "E") && enabled) {
        onToggleEdited();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
