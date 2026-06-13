import { useCallback, useEffect, useMemo, useRef } from "react";
import { api } from "./api";
import { useResource } from "./hooks/useResource";
import { useUrlState } from "./hooks/useUrlState";
import { isEdited } from "./lib/format";
import type { DexEntry } from "./types";
import { DeviceFrame } from "./components/DeviceFrame";
import { DexView } from "./components/DexView";
import { DetailLedger } from "./components/DetailLedger";
import { MovesTab } from "./components/tabs/MovesTab";
import { AbilitiesTab } from "./components/tabs/AbilitiesTab";
import { TypeChartTab } from "./components/tabs/TypeChartTab";
import { BehaviorsTab } from "./components/tabs/BehaviorsTab";

/**
 * The Canon dex app shell. Owns the dex fetch, the URL-persisted view state, and
 * the keyboard shortcuts; delegates each kind to its own screen. The detail
 * ledger overlays the dex when a species is open.
 */
export default function App() {
  const [view, update] = useUrlState();
  const dex = useResource<DexEntry[]>(api.dex);
  const searchRef = useRef<HTMLInputElement>(null);

  const all = useMemo(() => dex.data ?? [], [dex.data]);
  const editedCount = useMemo(() => all.filter(isEdited).length, [all]);

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
    return list;
  }, [all, view.editedOnly, view.query]);

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

  useGlobalKeys({
    onSearch: () => searchRef.current?.focus(),
    onToggleEdited: () => isDex && update({ editedOnly: !view.editedOnly }),
    onEscape: () => selectedEntry !== null && update({ selected: null }),
    enabled: isDex,
    hasSelection: selectedEntry !== null,
  });

  return (
    <DeviceFrame
      kind={view.kind}
      onKind={(kind) => update({ kind, selected: null })}
      query={view.query}
      onQuery={(query) => update({ query })}
      editedOnly={view.editedOnly}
      onEditedOnly={(editedOnly) => update({ editedOnly })}
      layout={view.layout}
      onLayout={(layout) => update({ layout })}
      searchRef={searchRef}
      readout={<Readout kind={view.kind} total={all.length} edited={editedCount} shown={filtered.length} />}
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
          entries={filtered}
          editedOnly={view.editedOnly}
          selected={view.selected}
          layout={view.layout}
          onOpen={handleOpen}
        />
      </div>
      {selectedEntry !== null && (
        <DetailLedger
          entry={selectedEntry}
          onClose={handleClose}
          onSaved={dex.reload}
          abilityOptions={abilityOptions}
        />
      )}
    </DeviceFrame>
  );
}

type KindScreenProps = {
  kind: ReturnType<typeof useUrlState>[0]["kind"];
  dexResource: ReturnType<typeof useResource<DexEntry[]>>;
  entries: DexEntry[];
  editedOnly: boolean;
  selected: string | null;
  layout: ReturnType<typeof useUrlState>[0]["layout"];
  onOpen: (id: string) => void;
};

function KindScreen({
  kind,
  dexResource,
  entries,
  editedOnly,
  selected,
  layout,
  onOpen,
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
    default:
      return (
        <DexView
          resource={dexResource}
          entries={entries}
          editedOnly={editedOnly}
          selected={selected}
          layout={layout}
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
