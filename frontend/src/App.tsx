import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { useResource } from "./hooks/useResource";
import { useUrlState } from "./hooks/useUrlState";
import { useTheme } from "./hooks/useTheme";
import { isEdited } from "./lib/format";
import { onDataChange } from "./lib/dataChange";
import { evalEntries, appendNameFilter } from "./lib/dexFilters";
import { cellMap } from "./lib/typeChartGrid";
import { stableMultiSort } from "./lib/dexSort";
import { expandEvoLines } from "./lib/evoLine";
import { searchTargetFor, promoteSearchToPill } from "./lib/searchDispatch";
import type { CanonicalMethod, DexEntry, KindKey, Move, Target, TargetNamespace, TypeChartCell } from "./types";
import { applyInlineEdit, previewInlineEdit, type InlineEdit } from "./lib/inlineEdit";
import { DeviceFrame } from "./components/DeviceFrame";
import { DexView } from "./components/DexView";
import type { DexViewPatch } from "./components/filters/DexControls";
import { DetailLedger } from "./components/DetailLedger";
import { MovesTab } from "./components/tabs/MovesTab";
import { AbilitiesTab } from "./components/tabs/AbilitiesTab";
import { TypeChartTab } from "./components/tabs/TypeChartTab";
import { TeamTab } from "./components/tabs/TeamTab";
import { BehaviorsTab } from "./components/tabs/BehaviorsTab";
import { TargetsTab } from "./components/tabs/TargetsTab";
import { LedgerTab } from "./components/tabs/LedgerTab";
import { ActiveTargetSwitcher } from "./components/targets/ActiveTargetSwitcher";
import { PatchDrawer } from "./components/targets/PatchDrawer";
import { MakeoverWorkbench } from "./components/makeover/MakeoverWorkbench";

/**
 * The Canon dex app shell. Owns the dex fetch, the URL-persisted view state, and
 * the keyboard shortcuts; delegates each kind to its own screen. The detail
 * ledger overlays the dex when a species is open.
 */
export default function App() {
  const [view, update] = useUrlState();
  const [theme, toggleTheme] = useTheme();
  // The dex fetch swaps to a Target's backdrop (target ⊕ Ruleset) when one is
  // set; otherwise it reads the base ⊕ Ruleset canon. Memoized by backdrop id so
  // useResource sees a stable fetcher and refetches only when the backdrop flips.
  const dexFetcher = useMemo(
    () => (view.backdrop ? api.targetDex(view.backdrop) : api.dex),
    [view.backdrop],
  );
  const dex = useResource<DexEntry[]>(dexFetcher);
  const moves = useResource<Move[]>(api.moves);
  // The active type chart (backdrop's fork ⊕ Ruleset, else base ⊕ Ruleset) —
  // powers the Type filter's matchup operators (weak to / SE against / …), so
  // they reflect the SAME chart the Type Chart and Team tabs show.
  const chartFetcher = useMemo(
    () => (view.backdrop ? api.targetTypeChart(view.backdrop) : api.typeChart),
    [view.backdrop],
  );
  const typeChart = useResource<TypeChartCell[]>(chartFetcher);
  const chartByKey = useMemo(
    () => (typeChart.data ? cellMap(typeChart.data) : null),
    [typeChart.data],
  );
  const targets = useResource<Target[]>(api.targets);
  // The canonical evolution-method catalog drives the editor's Method dropdown.
  // Static config — fetched once and threaded down like the option lists.
  const evolutionMethods = useResource<CanonicalMethod[]>(api.evolutionMethods);
  const reloadDex = dex.reload;
  const searchRef = useRef<HTMLInputElement>(null);
  const targetSelectRef = useRef<HTMLSelectElement>(null);

  // The patch workspace: which action (if any) opened the PatchDrawer. The drawer
  // always acts on the active target (view.backdrop); null = closed.
  const [patch, setPatch] = useState<{ trigger: "preview" | "apply" } | null>(
    null,
  );
  // Keep-alive tab host: once a kind is visited it stays mounted (hidden when
  // inactive), so switching back is instant — no remount, no re-running every
  // tab's useMemos or rebuilding its DOM. Lazy: a kind mounts only on first
  // visit. Adjusted during render (not an effect) so a new tab mounts in the
  // same pass instead of one commit later.
  // ponytail: hidden tabs still re-render on URL writes (they self-subscribe to
  // useUrlState); heavy work is useMemo'd so it's reconcile-only. If keystroke
  // lag ever shows up, thread an `active` prop and skip render work when hidden.
  const [visited, setVisited] = useState<Set<ViewSnapshot["kind"]>>(
    () => new Set([view.kind]),
  );
  if (!visited.has(view.kind)) {
    setVisited(new Set(visited).add(view.kind));
  }

  const activeTarget = useMemo(
    () => (targets.data ?? []).find((t) => t.id === view.backdrop) ?? null,
    [targets.data, view.backdrop],
  );
  // If the active target is cleared (Canon) or removed while the drawer is open,
  // there's nothing to patch — close it.
  useEffect(() => {
    if (patch !== null && activeTarget === null) setPatch(null);
  }, [patch, activeTarget]);

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

  // move name (lowercased) → type + category, so the profile learnset can tint
  // each row (type color), bold STAB, and italicize the mon's attacking category.
  const moveMeta = useMemo(() => {
    const byName = new Map<string, { type: string; category: string }>();
    for (const m of moves.data ?? [])
      byName.set(m.name.toLowerCase(), { type: m.type, category: m.category });
    return byName;
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
      list = list.filter((entry) => evalEntries(entry, view.filter, chartByKey));
    }
    // Evo-line expansion runs last so it widens the final match set, not an
    // intermediate one — a line-mate is kept even if it fails the filters.
    if (view.evoLine && list !== all) {
      list = expandEvoLines(list, all);
    }
    return list;
  }, [all, view.editedOnly, view.query, view.filter, view.evoLine, chartByKey]);

  // The table additionally sorts by the multi-key sort spec; the grid stays in
  // dex order. Only the visible view's list is consumed, so this is cheap.
  const tableRows = useMemo(
    () => stableMultiSort(filtered, view.sort),
    [filtered, view.sort],
  );
  const dexEntries = view.layout === "table" ? tableRows : filtered;

  const isDex = view.kind === "dex";
  const full = view.detail === "full";
  const selectedEntry =
    isDex && view.selected !== null
      ? all.find((entry) => entry.chrooked_id === view.selected) ?? null
      : null;
  // The Makeover Workbench takes over the screen when an anchor species is set in
  // the URL and it resolves in the loaded dex.
  const makeoverEntry =
    view.makeover !== null
      ? all.find((entry) => entry.chrooked_id === view.makeover) ?? null
      : null;

  // Stable so memo(DexCell) holds across the 1451-cell grid (`update` is stable).
  const handleOpen = useCallback(
    (id: string) => update({ selected: id }),
    [update],
  );
  const handleClose = useCallback(() => update({ selected: null }), [update]);

  // Step the open profile to the previous/next species in the CURRENT visible
  // order (filters + table sort applied), wrapping at the ends. Bound to the
  // header arrows and ←/→ in DetailLedger.
  const handleStep = useCallback(
    (delta: -1 | 1) => {
      if (view.selected === null || dexEntries.length === 0) return;
      const index = dexEntries.findIndex(
        (entry) => entry.chrooked_id === view.selected,
      );
      // Selected species filtered out of the list: step to the first entry.
      const next =
        index === -1
          ? 0
          : (index + delta + dexEntries.length) % dexEntries.length;
      update({ selected: dexEntries[next].chrooked_id });
    },
    [view.selected, dexEntries, update],
  );

  // Right-click inline table edit: fetch the species' raw Override (404 → none),
  // patch the one field to an overrides-only payload, PUT to the chosen scope
  // ("base" or "target:<slug>" — same contract as the modal editor). putSpecies
  // emits a data change, so the always-mounted dex refetches and the cell updates.
  //
  // Optimistic: the cell is patched in `dex` locally the instant the menu
  // submits, so the table updates before the network round-trip. A successful
  // PUT's emitDataChange → reload replaces the guess with the real merged row;
  // a failed PUT rolls the local patch back to the pre-edit snapshot.
  const handleInlineEdit = useCallback(
    async (entry: DexEntry, edit: InlineEdit, scope?: string) => {
      dex.mutate((rows) =>
        rows?.map((row) =>
          row.chrooked_id === entry.chrooked_id ? previewInlineEdit(row, edit) : row,
        ) ?? rows,
      );
      try {
        const raw = await api.speciesOverride(entry.chrooked_id).catch(() => null);
        await api.putSpecies(entry.chrooked_id, applyInlineEdit(entry, raw, edit), scope);
      } catch (error) {
        dex.mutate((rows) =>
          rows?.map((row) => (row.chrooked_id === entry.chrooked_id ? entry : row)) ?? rows,
        );
        throw error;
      }
    },
    [dex],
  );

  // Backdrop's Override namespace — lets the inline edit menu offer a scope
  // choice (mirrors SpeciesEditor's namespace resolution; unbound → null → base).
  const [inlineNamespace, setInlineNamespace] = useState<TargetNamespace | null>(null);
  useEffect(() => {
    if (!view.backdrop) {
      setInlineNamespace(null);
      return;
    }
    const controller = new AbortController();
    api
      .targetNamespace(view.backdrop, controller.signal)
      .then((ns) => !controller.signal.aborted && setInlineNamespace(ns))
      .catch(() => !controller.signal.aborted && setInlineNamespace(null));
    return () => controller.abort();
  }, [view.backdrop]);

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
  // The header switcher sets the active target (the backdrop) without leaving
  // the current tab — backdrop already redraws dex/moves/abilities/type-chart.
  const handleSetActiveTarget = useCallback(
    (targetId: string | null) => update({ backdrop: targetId }),
    [update],
  );
  const handleOpenPatch = useCallback(
    (trigger: "preview" | "apply") => setPatch({ trigger }),
    [],
  );
  const handleManageTargets = useCallback(
    () => update({ kind: "targets", selected: null }),
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

  // Escape unwinds one layer at a time: the patch drawer first (most recent
  // foreground), then a full-page detail collapses back to the side panel, then
  // the detail ledger closes.
  const handleEscape = useCallback(() => {
    if (patch !== null) {
      setPatch(null);
      return;
    }
    if (selectedEntry !== null && view.detail === "full") {
      update({ detail: "panel" });
      return;
    }
    if (selectedEntry !== null) update({ selected: null });
  }, [patch, selectedEntry, view.detail, update]);

  useGlobalKeys({
    onSearch: () => searchRef.current?.focus(),
    onToggleEdited: () =>
      isEditedFilterable && update({ editedOnly: !view.editedOnly }),
    onSwitchTarget: () => targetSelectRef.current?.focus(),
    onToggleFull: () =>
      selectedEntry !== null && update({ detail: full ? "panel" : "full" }),
    onEscape: handleEscape,
    enabled: isEditedFilterable,
    hasSelection: selectedEntry !== null || patch !== null,
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
      evoLine={view.evoLine}
      onEvoLine={(evoLine) => update({ evoLine })}
      onSearchEnter={handleSearchEnter}
      layout={view.layout}
      onLayout={(layout) => update({ layout })}
      theme={theme}
      onToggleTheme={toggleTheme}
      searchRef={searchRef}
      targetBar={
        <ActiveTargetSwitcher
          targets={targets.data ?? []}
          activeId={view.backdrop ?? null}
          onSetActive={handleSetActiveTarget}
          onPreview={() => handleOpenPatch("preview")}
          onApply={() => handleOpenPatch("apply")}
          onManage={handleManageTargets}
          busy={patch !== null}
          selectRef={targetSelectRef}
        />
      }
      readout={
        <Readout kind={view.kind} total={all.length} edited={editedCount} shown={filtered.length} />
      }
    >
      {makeoverEntry !== null ? (
        <MakeoverWorkbench
          entry={makeoverEntry}
          allEntries={all}
          moves={moves.data ?? []}
          stage={view.makeoverStage}
          onStage={(stage) => update({ makeoverStage: stage })}
          onExit={() => update({ makeover: null, makeoverStage: null })}
          onSaved={reloadDex}
          moveOptions={moveOptions}
          abilityOptions={abilityOptions}
          targets={targets.data ?? []}
          activeTargetId={view.backdrop}
          backdropTargetId={view.backdrop}
        />
      ) : (
      <>
      {/* Background is inert while a species is open — in both modes. In panel
          mode it's the modal focus trap; in full mode the opaque pane fully
          covers the grid, so inert keeps focus/AT out of the invisible list
          behind it (the rail lives outside this layer and stays interactive).
          `inert` is spread as a raw attribute for React 18 (typed in React 19). */}
      <div
        className="device__layer"
        {...(selectedEntry !== null
          ? ({ inert: "" } as Record<string, string>)
          : {})}
      >
        {[...visited].map((kind) => (
          <div
            key={kind}
            className="device__tabpane"
            hidden={kind !== view.kind}
          >
            <KindScreen
              kind={kind}
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
              backdropTargetId={view.backdrop}
              abilityOptions={abilityOptions}
              speciesOptions={speciesOptions}
              evolutionMethods={evolutionMethods.data ?? []}
              onInlineEdit={handleInlineEdit}
              inlineScopeTarget={inlineNamespace}
            />
          </div>
        ))}
      </div>
      {selectedEntry !== null && (
        <DetailLedger
          entry={selectedEntry}
          onClose={handleClose}
          onStep={handleStep}
          onSaved={dex.reload}
          onNavigate={handleNavigate}
          full={full}
          onToggleFull={() => update({ detail: full ? "panel" : "full" })}
          abilityOptions={abilityOptions}
          moveOptions={moveOptions}
          moveMeta={moveMeta}
          speciesOptions={speciesOptions}
          evolutionMethods={evolutionMethods.data ?? []}
          backdropTargetId={view.backdrop}
          dexEntries={all}
        />
      )}
      {patch !== null && activeTarget !== null && (
        <PatchDrawer
          target={activeTarget}
          trigger={patch.trigger}
          onClose={() => setPatch(null)}
          onApplied={dex.reload}
        />
      )}
      </>
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
  backdropTargetId?: string | null;
  abilityOptions?: readonly string[];
  speciesOptions?: readonly string[];
  evolutionMethods?: readonly CanonicalMethod[];
  onInlineEdit?: (entry: DexEntry, edit: InlineEdit, scope?: string) => Promise<void>;
  inlineScopeTarget?: TargetNamespace | null;
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
  backdropTargetId,
  abilityOptions,
  speciesOptions,
  evolutionMethods,
  onInlineEdit,
  inlineScopeTarget,
}: KindScreenProps) {
  switch (kind) {
    case "moves":
      return <MovesTab backdropTargetId={backdropTargetId} />;
    case "abilities":
      return <AbilitiesTab backdropTargetId={backdropTargetId} />;
    case "type-chart":
      return <TypeChartTab />;
    case "team":
      return <TeamTab />;
    case "behaviors":
      return <BehaviorsTab />;
    case "targets":
      return <TargetsTab onViewBackdrop={onViewBackdrop} />;
    case "ledger":
      return <LedgerTab />;
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
          backdropTargetId={backdropTargetId}
          abilityOptions={abilityOptions}
          speciesOptions={speciesOptions}
          evolutionMethods={evolutionMethods}
          onInlineEdit={onInlineEdit}
          inlineScopeTarget={inlineScopeTarget}
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
    return <span>targets · register &amp; manage</span>;
  }
  if (kind === "team") {
    return <span>team · matchup planner</span>;
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
  onSwitchTarget: () => void;
  onToggleFull: () => void;
  onEscape: () => void;
  enabled: boolean;
  hasSelection: boolean;
};

/** Global keyboard shortcuts: `/` focuses search, `e` toggles the edited filter,
    `t` focuses the active-target switcher, `f` toggles full-page detail (only
    while a species is open), Escape closes the open overlay. Shortcuts ignore
    keystrokes inside form fields. */
function useGlobalKeys(handlers: KeyHandlers): void {
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const {
        onSearch,
        onToggleEdited,
        onSwitchTarget,
        onToggleFull,
        onEscape,
        enabled,
        hasSelection,
      } = ref.current;
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
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if (inField || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      if (event.key === "/") {
        event.preventDefault();
        onSearch();
      } else if ((event.key === "e" || event.key === "E") && enabled) {
        onToggleEdited();
      } else if (event.key === "t" || event.key === "T") {
        event.preventDefault();
        onSwitchTarget();
      } else if (event.key === "f" || event.key === "F") {
        // Toggle full-page detail; onToggleFull is a no-op with no species open.
        event.preventDefault();
        onToggleFull();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
