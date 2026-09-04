import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { useResource } from "./hooks/useResource";
import { useUrlState } from "./hooks/useUrlState";
import { useTheme } from "./hooks/useTheme";
import { isEdited } from "./lib/format";
import { evalEntries } from "./lib/dexFilters";
import { cellMap } from "./lib/typeChartGrid";
import { stableMultiSort } from "./lib/dexSort";
import { expandEvoLines } from "./lib/evoLine";
import { searchTargetFor, syncSearchToNameFilter, commitSearchPill } from "./lib/searchDispatch";
import type { Ability, CanonicalMethod, DexEntry, KindKey, Move, Target, TargetNamespace, TypeChartCell } from "./types";
import { EntityInfoProvider } from "./lib/entityInfo";
import { applyInlineEdit, previewInlineEdit, type InlineEdit } from "./lib/inlineEdit";
import { DeviceFrame, RAIL_KIND_ORDER } from "./components/DeviceFrame";
import { DexView } from "./components/DexView";
import type { DexViewPatch } from "./components/filters/DexControls";
import { DetailLedger } from "./components/DetailLedger";
import { MovesTab } from "./components/tabs/MovesTab";
import { AbilitiesTab } from "./components/tabs/AbilitiesTab";
import { TypeChartTab } from "./components/tabs/TypeChartTab";
import { TeamTab } from "./components/tabs/TeamTab";
import { StatusesTab } from "./components/tabs/StatusesTab";
import { BehaviorsTab } from "./components/tabs/BehaviorsTab";
import { TargetsTab } from "./components/tabs/TargetsTab";
import { LedgerTab } from "./components/tabs/LedgerTab";
import { useGamepad, type GamepadAction } from "./hooks/useGamepad";
import { activateFocused, clearPadFocus, focusInDirection } from "./lib/spatialNav";
import { GamepadProbe } from "./components/GamepadProbe";
import { ActiveTargetSwitcher } from "./components/targets/ActiveTargetSwitcher";
import { PatchDrawer } from "./components/targets/PatchDrawer";
import { MakeoverWorkbench } from "./components/makeover/MakeoverWorkbench";
import { ParkedMakeoverDock } from "./components/makeover/ParkedMakeover";
import type { MakeoverActivity } from "./lib/makeoverActivity";
import type { Stage } from "./lib/makeoverStages";
import { uid } from "./lib/uid";

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
  // Moves and abilities are fetched app-wide for the same two reasons the dex is:
  // they power the hover cards / option lists everywhere, AND fetching them here
  // warms the shared `useResource` cache so the Moves and Abilities tabs paint
  // instantly on first open instead of showing a skeleton. Backdrop-aware and
  // memoized exactly like `dexFetcher`, so the tabs resolve the SAME fetcher
  // identity and hit that cache.
  const movesFetcher = useMemo(
    () => (view.backdrop ? api.targetMoves(view.backdrop) : api.moves),
    [view.backdrop],
  );
  const abilitiesFetcher = useMemo(
    () => (view.backdrop ? api.targetAbilities(view.backdrop) : api.abilities),
    [view.backdrop],
  );
  const moves = useResource<Move[]>(movesFetcher);
  const abilityRecords = useResource<Ability[]>(abilitiesFetcher);
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

  const all = useMemo(() => dex.data ?? [], [dex.data]);
  const editedCount = useMemo(() => all.filter(isEdited).length, [all]);

  // A party id that no longer resolves against the active dex is a phantom: it
  // renders no card but still counts toward the six-cap, so a five-mon team
  // reads "full". Prune once the dex is loaded so the cap matches the screen.
  useEffect(() => {
    if (!dex.data || dex.data.length === 0 || view.party.length === 0) return;
    const known = new Set(dex.data.map((entry) => entry.chrooked_id));
    const pruned = view.party.filter((member) => known.has(member.id));
    if (pruned.length !== view.party.length) update({ party: pruned });
  }, [dex.data, view.party, update]);

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

  // Row predicates: edited-only, then the boolean filter builder. The rail
  // search filters THROUGH the builder — the sync effect below keeps it as a
  // Name pill in `view.filter`, so there is one filtering path, not two.
  // `view.filter`/`view.sort` are safe memo deps: useUrlState caches the whole
  // ViewState by the raw query string, so these arrays keep a stable reference
  // until the URL changes.
  const filtered = useMemo(() => {
    let list = all;
    if (view.editedOnly) {
      list = list.filter(isEdited);
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
  }, [all, view.editedOnly, view.filter, view.evoLine, chartByKey]);

  // Both grid and table honor the multi-key sort spec (an empty spec is a stable
  // no-op, so an unsorted view keeps dex order). Only the visible view's list is
  // consumed, so this is cheap.
  const dexEntries = useMemo(
    () => stableMultiSort(filtered, view.sort),
    [filtered, view.sort],
  );

  const isDex = view.kind === "dex";
  const full = view.detail === "full";
  // The profile ledger overlays the dex AND the Team tab: opening a party
  // member's profile should not throw the user out of the team they are
  // building, so Team opens the same panel in place. Every other kind resolves
  // `selected` against its own entity, so the ledger stays out of them.
  const canShowProfile = isDex || view.kind === "team";
  const selectedEntry =
    canShowProfile && view.selected !== null
      ? all.find((entry) => entry.chrooked_id === view.selected) ?? null
      : null;
  // The Makeover Workbench takes over the screen when an anchor species is set in
  // the URL and it resolves in the loaded dex.
  // PARKED: "← dex"/Esc dismisses the workbench without abandoning it — the URL
  // drops back to the dex but the workbench stays MOUNTED (hidden), so an
  // unlocked draft (a proposed-but-not-locked learnset) survives the detour and
  // an in-flight suggest keeps processing. Several makeovers can be parked at
  // once (the dock, oldest first); the URL always names the one on screen.
  // ponytail: mount-scoped only — a page reload still drops parked runs.
  const [parked, setParked] = useState<{ id: string; stage: Stage | null }[]>([]);
  // Per-species propose activity, fed by each mounted workbench — the dock LED.
  const [makeoverActivity, setMakeoverActivity] = useState<Record<string, MakeoverActivity>>({});
  const activeMakeoverEntry =
    view.makeover !== null
      ? all.find((entry) => entry.chrooked_id === view.makeover) ?? null
      : null;

  // Every mounted makeover: the parked ones (dock order) plus the URL-active one.
  // One keyed list, so parking/resuming re-flags a host instead of remounting it.
  const mountedMakeovers = useMemo(() => {
    const hosts = parked.flatMap((item) => {
      const entry = all.find((e) => e.chrooked_id === item.id);
      return entry ? [{ entry, parkedStage: item.stage, isActive: item.id === view.makeover }] : [];
    });
    if (activeMakeoverEntry !== null && !parked.some((p) => p.id === view.makeover)) {
      hosts.push({ entry: activeMakeoverEntry, parkedStage: null, isActive: true });
    }
    return hosts;
  }, [parked, all, view.makeover, activeMakeoverEntry]);

  // A makeover opened from the URL promotes its parked copy (same mount, now on
  // screen) — drop it from the dock.
  useEffect(() => {
    if (view.makeover === null) return;
    setParked((prev) =>
      prev.some((p) => p.id === view.makeover) ? prev.filter((p) => p.id !== view.makeover) : prev,
    );
  }, [view.makeover]);

  const handleParkMakeover = useCallback(() => {
    if (view.makeover === null) return;
    const id = view.makeover;
    const stage = view.makeoverStage;
    setParked((prev) => [...prev.filter((p) => p.id !== id), { id, stage }]);
    update({ makeover: null, makeoverStage: null, makeoverSelect: null });
  }, [view.makeover, view.makeoverStage, update]);

  const handleResumeMakeover = useCallback(
    (id: string) => {
      const item = parked.find((p) => p.id === id);
      if (item === undefined) return;
      update({ makeover: item.id, makeoverStage: item.stage, makeoverSelect: null });
    },
    [parked, update],
  );

  const handleDiscardParked = useCallback((id: string) => {
    setParked((prev) => prev.filter((p) => p.id !== id));
    setMakeoverActivity((prev) => {
      if (!(id in prev)) return prev;
      const { [id]: _dropped, ...rest } = prev;
      return rest;
    });
  }, []);

  // The finished (or abandoned-for-good) run: unmounts the active workbench.
  const handleCloseMakeover = useCallback(() => {
    if (view.makeover !== null) handleDiscardParked(view.makeover);
    update({ makeover: null, makeoverStage: null, makeoverSelect: null });
  }, [view.makeover, handleDiscardParked, update]);

  const handleMakeoverActivity = useCallback((id: string, activity: MakeoverActivity) => {
    setMakeoverActivity((prev) => (prev[id] === activity ? prev : { ...prev, [id]: activity }));
  }, []);

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
      // Stepping walks the DEX's visible order, which means nothing on the Team
      // tab — a party member's neighbours there are the dex's filter results,
      // not the team. Off the dex, the arrows simply do nothing.
      if (!isDex) return;
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
    [isDex, view.selected, dexEntries, update],
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

  // The rail search IS a Name filter pill: this effect live-syncs a search-owned
  // pill (a fixed sentinel id) into the ACTIVE entity's filter param — added on
  // the first keystroke, updated as the text changes, removed when the box
  // empties — so the term shows in the filter bar and composes with other pills.
  // Runs on tab switch too, so the term follows you onto the new tab's builder;
  // a tab left behind self-heals its pill on the next visit. Type Chart has no
  // pills (searchTargetFor → null): its search selects a type live via
  // `view.query`. All three targets write through the URL (chrooked:urlchange),
  // which useUrlState and the tabs' control hooks both subscribe to.
  useEffect(() => {
    const target = searchTargetFor(view.kind);
    if (target !== null) {
      syncSearchToNameFilter(target, view.query);
    }
  }, [view.kind, view.query]);

  // Enter keeps the live pill: the search-owned pill is re-id'd to a permanent
  // one (or dropped when a duplicate user pill exists) and the box clears, so
  // clearing no longer removes it — that's how you stack several Name pills.
  const handleSearchEnter = useCallback(() => {
    const target = searchTargetFor(view.kind);
    if (target === null) {
      return;
    }
    if (commitSearchPill(target, uid())) {
      update({ query: "" });
    }
  }, [view.kind, update]);

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

  // `?gamepad=probe` shows a live controller readout — the only way to confirm
  // this hardware's button indices, which cannot be checked from a dev machine.
  // Read once: it is a debugging entry point, not view state.
  const [isGamepadProbe] = useState(
    () => new URLSearchParams(window.location.search).get("gamepad") === "probe",
  );

  // A touch takes over from the controller: drop the D-pad cursor so its ring
  // does not sit somewhere the user has stopped looking, implying the next A
  // press will act there.
  useEffect(() => {
    const onPointer = (event: PointerEvent) => {
      if (event.pointerType !== "gamepad") clearPadFocus();
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, []);

  // Arrow keys drive the same cursor as the D-pad, but only once focus is
  // already on something inside the screen area — so arrows still scroll the
  // page normally until you have actually entered the grid, and never fight a
  // text field or a <select>. This is ordinary grid behaviour at the desk, and
  // it means the controller path and the keyboard path are the same code.
  useEffect(() => {
    const DIRECTIONS: Record<string, "up" | "down" | "left" | "right"> = {
      ArrowUp: "up",
      ArrowDown: "down",
      ArrowLeft: "left",
      ArrowRight: "right",
    };
    function onKeyDown(event: KeyboardEvent) {
      const direction = DIRECTIONS[event.key];
      if (!direction || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (!target || target === document.body) return;
      const tag = target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable) {
        return;
      }
      if (!target.closest("main")) return;
      event.preventDefault();
      focusInDirection(direction);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  // The handheld's physical controls, mapped onto real DOM focus rather than a
  // bespoke cursor: the D-pad moves focus, A clicks whatever it lands on. That
  // reuses every existing click handler and focus-visible style, and works on
  // the grid, the table and the rail without any of them knowing about it.
  useGamepad(
    useCallback(
      (action: GamepadAction) => {
        switch (action) {
          case "up":
          case "down":
          case "left":
          case "right":
            focusInDirection(action);
            break;
          case "confirm": // the button printed "A" — open what the cursor is on
            activateFocused();
            break;
          case "cancel": // the button printed "B" — back out of whatever is open
            handleEscape();
            break;
          case "l1":
          case "r1": {
            const order = RAIL_KIND_ORDER;
            const at = order.indexOf(view.kind);
            // Shoulder buttons only step the rail kinds; from Team/Ledger
            // (which are not in the rail) they land on the first one.
            const next =
              at === -1
                ? order[0]
                : order[(at + (action === "r1" ? 1 : -1) + order.length) % order.length];
            update({ kind: next, selected: null });
            break;
          }
        }
      },
      [handleEscape, update, view.kind],
    ),
  );

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
    <EntityInfoProvider moves={moves.data} abilities={abilityRecords.data}>
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
      {/* Every open makeover stays mounted (hidden while parked) so unlocked
          drafts and in-flight suggests survive; keyed by species so a resumed
          host keeps its state and a new species starts clean. */}
      {mountedMakeovers.map(({ entry, parkedStage, isActive }) => (
        <div className="mk-host" hidden={!isActive} key={entry.chrooked_id}>
          <MakeoverWorkbench
            entry={entry}
            allEntries={all}
            moves={moves.data ?? []}
            stage={isActive ? view.makeoverStage : parkedStage}
            initialSelected={isActive ? view.makeoverSelect : null}
            // A parked workbench keeps running (its tail can advance stages) but
            // must not write the URL while another view owns the screen.
            onStage={isActive ? (stage) => update({ makeoverStage: stage }) : () => undefined}
            paused={!isActive}
            onPark={handleParkMakeover}
            onExit={handleCloseMakeover}
            onActivity={(activity) => handleMakeoverActivity(entry.chrooked_id, activity)}
            onSaved={reloadDex}
            moveOptions={moveOptions}
            abilityOptions={abilityOptions}
            targets={targets.data ?? []}
            activeTargetId={view.backdrop}
            backdropTargetId={view.backdrop}
          />
        </div>
      ))}
      {activeMakeoverEntry !== null ? null : (
      <>
      <ParkedMakeoverDock
        items={parked.flatMap((item) => {
          const entry = all.find((e) => e.chrooked_id === item.id);
          return entry
            ? [{ id: item.id, name: entry.name, activity: makeoverActivity[item.id] ?? "idle" }]
            : [];
        })}
        onResume={handleResumeMakeover}
        onDiscard={handleDiscardParked}
      />
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
    {isGamepadProbe && <GamepadProbe />}
    </EntityInfoProvider>
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
    case "statuses":
      return <StatusesTab />;
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
