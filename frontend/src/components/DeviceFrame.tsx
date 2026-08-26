import { useEffect, useId, useRef, useState } from "react";
import type { ComponentType, ReactNode, RefObject } from "react";
import type { KindKey } from "../types";
import type { DexLayout } from "../hooks/useUrlState";
import type { Theme } from "../hooks/useTheme";
import { useCompactShell } from "../hooks/useMediaQuery";
import { ReseedNote } from "./ReseedNote";
import {
  IconAbilities,
  IconBehaviors,
  IconClose,
  IconFilters,
  IconGridView,
  IconLedger,
  IconTable,
  IconSpecies,
  IconMoves,
  IconStatuses,
  IconTeam,
  IconTypeChart,
} from "./icons";
import "./device-frame.css";

type TabDef = { key: KindKey; label: string; Icon: ComponentType<{ className?: string }> };

// The rail lists the dex-data browsing kinds — the things you look up. Targets
// (registration) is reached from the header active-target switcher.
const KIND_TABS: TabDef[] = [
  { key: "dex", label: "Species", Icon: IconSpecies },
  { key: "moves", label: "Moves", Icon: IconMoves },
  { key: "abilities", label: "Abilities", Icon: IconAbilities },
  { key: "type-chart", label: "Type Chart", Icon: IconTypeChart },
  { key: "statuses", label: "Statuses", Icon: IconStatuses },
  { key: "behaviors", label: "Behaviors", Icon: IconBehaviors },
];

/** The rail's left-to-right order, for anything that steps through tabs (the
    controller's shoulder buttons). Exported so the stepping order and the
    rendered order cannot drift. */
export const RAIL_KIND_ORDER: readonly KindKey[] = KIND_TABS.map((tab) => tab.key);

// The header navbar carries the two kinds that are NOT dex lookups: a planner
// you build in (Team) and the change record (Ledger). Keeping them out of the
// rail stops the rail from mixing "what exists" with "what I'm doing".
const HEADER_TABS: TabDef[] = [
  { key: "team", label: "Team", Icon: IconTeam },
  { key: "ledger", label: "Ledger", Icon: IconLedger },
];

type Props = {
  kind: KindKey;
  onKind: (kind: KindKey) => void;
  query: string;
  onQuery: (query: string) => void;
  /** Whether the rail search is active for this kind (dex / moves / abilities). */
  searchable: boolean;
  editedOnly: boolean;
  onEditedOnly: (on: boolean) => void;
  /** Expand every dex match to its whole evolution line. */
  evoLine: boolean;
  onEvoLine: (on: boolean) => void;
  /** Keep the search's live Name filter pill as a permanent one (Enter). */
  onSearchEnter: () => void;
  layout: DexLayout;
  onLayout: (layout: DexLayout) => void;
  theme: Theme;
  onToggleTheme: () => void;
  readout: ReactNode;
  /** The active-target switcher — the highest-hierarchy control (drives the
      backdrop across every tab), so it sits in the header, not the rail. */
  targetBar?: ReactNode;
  searchRef: RefObject<HTMLInputElement>;
  children: ReactNode;
};

/**
 * The handheld-style chrome: a device header with a segmented readout, a left
 * rail (search, the edited filter, the kind tabs), and the main screen.
 *
 * Two shells, one markup tree. The roomy shell is the desk layout: a 232px rail
 * with text labels and the search and filters living in it. The **compact**
 * shell — driven by `useCompactShell`, which triggers on short viewports as
 * well as narrow ones — collapses the header to a single row, turns the rail
 * into an icon column, and moves the search into the header with the filters
 * behind a sheet. It exists because this app is used on a handheld in landscape
 * (833x468), where height, not width, is what runs out.
 *
 * The search input is rendered exactly once and relocated between the two
 * hosts, so `searchRef`, focus, and IME state survive a viewport change.
 */
export function DeviceFrame({
  kind,
  onKind,
  query,
  onQuery,
  searchable,
  editedOnly,
  onEditedOnly,
  evoLine,
  onEvoLine,
  onSearchEnter,
  layout,
  onLayout,
  theme,
  onToggleTheme,
  readout,
  targetBar,
  searchRef,
  children,
}: Props) {
  const compact = useCompactShell();
  const isDex = kind === "dex";
  const searchPlaceholder =
    kind === "moves"
      ? "Search moves"
      : kind === "abilities"
        ? "Search abilities"
        : kind === "type-chart"
          ? "Search types"
          : "Search dex";

  const filters = (
    <DexFilters
      isDex={isDex}
      editedOnly={editedOnly}
      onEditedOnly={onEditedOnly}
      evoLine={evoLine}
      onEvoLine={onEvoLine}
      layout={layout}
      onLayout={onLayout}
    />
  );

  const search = (
    <div className="device__search" data-disabled={!searchable}>
      <span className="device__search-key mono" aria-hidden="true">
        /
      </span>
      <input
        ref={searchRef}
        type="search"
        className="device__search-input"
        placeholder={searchPlaceholder}
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            onSearchEnter();
          }
        }}
        disabled={!searchable}
        aria-label={`${searchPlaceholder} by name. Filters as you type; press Enter to keep the term as a Name filter.`}
      />
      {searchable && query.trim() !== "" && (
        <kbd
          className="device__search-enter mono"
          title="Press Enter to keep as a Name filter"
          aria-hidden="true"
        >
          ↵
        </kbd>
      )}
    </div>
  );

  return (
    <div className="device" id="app-shell" data-compact={compact}>
      <header className="device__header">
        <div className="device__brand">
          <span className="device__lamp" aria-hidden="true" />
          <h1 className="device__title">
            chrooked<span className="device__title-dim">·pokedex</span>
          </h1>
        </div>
        {targetBar && <div className="device__target-bar">{targetBar}</div>}

        {/* Compact only: the search is the primary action on a handheld — you
            open this to look something up mid-game — so it rides in the header
            where the rail has no room for it. */}
        {compact && <div className="device__header-search">{search}</div>}

        <div className="device__header-right">
          {compact && <FilterSheet label="Filters">{filters}</FilterSheet>}
          <nav className="device__header-nav" aria-label="Workspaces">
            {HEADER_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                id={`header-tab-${tab.key}`}
                className="device__nav-tab"
                data-active={kind === tab.key}
                aria-current={kind === tab.key ? "true" : undefined}
                title={compact ? tab.label : undefined}
                onClick={() => onKind(tab.key)}
              >
                <tab.Icon className="device__nav-icon" />
                <span className="device__nav-label">{tab.label}</span>
              </button>
            ))}
          </nav>
          <div className="device__readout mono" id="dex-summary">
            {readout}
          </div>
          <div
            className="device__layout device__theme"
            id="theme-toggle"
            role="group"
            aria-label="Theme"
          >
            <button
              type="button"
              className="device__layout-btn"
              data-active={theme === "dark"}
              aria-pressed={theme === "dark"}
              onClick={() => theme !== "dark" && onToggleTheme()}
            >
              Dark
            </button>
            <button
              type="button"
              className="device__layout-btn"
              data-active={theme === "light"}
              aria-pressed={theme === "light"}
              onClick={() => theme !== "light" && onToggleTheme()}
            >
              Light
            </button>
          </div>
        </div>
      </header>

      <div className="device__body">
        <nav className="device__rail" aria-label="Sections">
          {!compact && search}
          {!compact && filters}

          <ul className="device__tabs">
            {KIND_TABS.map((tab) => (
              <li key={tab.key}>
                <button
                  type="button"
                  className="device__tab"
                  data-active={kind === tab.key}
                  aria-current={kind === tab.key ? "true" : undefined}
                  title={compact ? tab.label : undefined}
                  onClick={() => onKind(tab.key)}
                >
                  <tab.Icon className="device__tab-icon" />
                  <span className="device__tab-label">{tab.label}</span>
                </button>
              </li>
            ))}
          </ul>

          {/* Compact only: the Grid/Table switch lives in the rail rather than
              in the filter sheet. It is a view mode, not a filter, and burying
              a mode behind a menu means nobody finds it — which is exactly what
              happened when it was in the sheet. One button showing the mode you
              would switch TO, so it needs no label. */}
          {compact && isDex && (
            <button
              type="button"
              className="device__tab device__view-toggle"
              id="rail-view-toggle"
              title={layout === "grid" ? "Switch to table" : "Switch to grid"}
              aria-label={layout === "grid" ? "Switch to table view" : "Switch to grid view"}
              onClick={() => onLayout(layout === "grid" ? "table" : "grid")}
            >
              {layout === "grid" ? (
                <IconTable className="device__tab-icon" />
              ) : (
                <IconGridView className="device__tab-icon" />
              )}
            </button>
          )}

          {!compact && kind !== "behaviors" && <ReseedNote />}
        </nav>

        <main className="device__screen">{children}</main>
      </div>
    </div>
  );
}

/** The filter controls, rendered into the rail on the desk and into a sheet on
    a handheld. One definition so the two hosts can never drift apart. */
function DexFilters({
  isDex,
  editedOnly,
  onEditedOnly,
  evoLine,
  onEvoLine,
  layout,
  onLayout,
}: {
  isDex: boolean;
  editedOnly: boolean;
  onEditedOnly: (on: boolean) => void;
  evoLine: boolean;
  onEvoLine: (on: boolean) => void;
  layout: DexLayout;
  onLayout: (layout: DexLayout) => void;
}) {
  return (
    <div className="device__filters">
      <button
        type="button"
        className="device__filter"
        data-on={editedOnly}
        aria-pressed={editedOnly}
        onClick={() => onEditedOnly(!editedOnly)}
      >
        <span className="device__filter-lamp" aria-hidden="true" />
        Edited only
        <kbd className="device__kbd mono">E</kbd>
      </button>

      {isDex && (
        <button
          type="button"
          className="device__filter"
          id="rail-evo-line"
          data-on={evoLine}
          aria-pressed={evoLine}
          title="Any match also shows its pre-evolutions and evolutions"
          onClick={() => onEvoLine(!evoLine)}
        >
          <span className="device__filter-lamp" aria-hidden="true" />
          Whole evo line
        </button>
      )}

      {isDex && (
        <div className="device__layout" role="group" aria-label="Dex layout">
          <button
            type="button"
            className="device__layout-btn"
            data-active={layout === "grid"}
            aria-pressed={layout === "grid"}
            onClick={() => onLayout("grid")}
          >
            Grid
          </button>
          <button
            type="button"
            className="device__layout-btn"
            data-active={layout === "table"}
            aria-pressed={layout === "table"}
            onClick={() => onLayout("table")}
          >
            Table
          </button>
        </div>
      )}
    </div>
  );
}

/** A small popover holding the filters on the compact shell. Closes on Escape,
    on outside pointer-down, and after a filter is toggled is deliberately left
    OPEN — you usually set two of these at once, and a sheet that vanishes after
    each tap turns one decision into three round-trips. */
function FilterSheet({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onDown = (event: PointerEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  return (
    <div className="device__sheet-wrap" ref={wrapRef}>
      <button
        type="button"
        className="device__sheet-trigger"
        id="filter-sheet-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={label}
        title={label}
        onClick={() => setOpen((was) => !was)}
      >
        {open ? (
          <IconClose className="device__nav-icon" />
        ) : (
          <IconFilters className="device__nav-icon" />
        )}
      </button>
      {open && (
        <div className="device__sheet" id={panelId} role="group" aria-label={label}>
          {children}
        </div>
      )}
    </div>
  );
}
