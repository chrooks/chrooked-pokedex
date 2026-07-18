import type { ReactNode, RefObject } from "react";
import type { KindKey } from "../types";
import type { DexLayout } from "../hooks/useUrlState";
import type { Theme } from "../hooks/useTheme";
import { ReseedNote } from "./ReseedNote";
import "./device-frame.css";

// The rail lists the dex-data browsing kinds. Targets (registration) is reached
// from the header active-target switcher; the Ledger lives in the header navbar.
const KIND_TABS: { key: KindKey; label: string }[] = [
  { key: "dex", label: "Species" },
  { key: "moves", label: "Moves" },
  { key: "abilities", label: "Abilities" },
  { key: "type-chart", label: "Type Chart" },
  { key: "behaviors", label: "Behaviors" },
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
  /** Promote the current search term to a Name filter pill (Enter in search). */
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
 * rail (search, the edited filter, the kind tabs), and the main screen. The
 * search applies wherever `searchable` is set; the "Edited only" filter applies
 * on the dex, moves, abilities, and type-chart (the layout toggle stays
 * dex-only).
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
  const isDex = kind === "dex";
  const searchPlaceholder =
    kind === "moves"
      ? "Search moves"
      : kind === "abilities"
        ? "Search abilities"
        : kind === "type-chart"
          ? "Search types"
          : "Search dex";
  return (
    <div className="device" id="app-shell">
      <header className="device__header">
        <div className="device__brand">
          <span className="device__lamp" aria-hidden="true" />
          <h1 className="device__title">
            chrooked<span className="device__title-dim">·pokedex</span>
          </h1>
        </div>
        {targetBar && <div className="device__target-bar">{targetBar}</div>}
        <div className="device__header-right">
          <nav className="device__header-nav" aria-label="Records">
            <button
              type="button"
              className="device__nav-tab"
              data-active={kind === "ledger"}
              aria-current={kind === "ledger" ? "true" : undefined}
              onClick={() => onKind("ledger")}
            >
              Ledger
            </button>
          </nav>
          <div className="device__readout mono" id="dex-summary">
            {readout}
          </div>
          <div
            className="device__layout"
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
              aria-label={`${searchPlaceholder} by name. Press Enter to add it as a Name filter.`}
            />
            {searchable && query.trim() !== "" && (
              <kbd
                className="device__search-enter mono"
                title="Press Enter to add as a Name filter"
                aria-hidden="true"
              >
                ↵
              </kbd>
            )}
          </div>

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
            <div
              className="device__layout"
              role="group"
              aria-label="Dex layout"
            >
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

          <ul className="device__tabs">
            {KIND_TABS.map((tab) => (
              <li key={tab.key}>
                <button
                  type="button"
                  className="device__tab"
                  data-active={kind === tab.key}
                  aria-current={kind === tab.key ? "true" : undefined}
                  onClick={() => onKind(tab.key)}
                >
                  {tab.label}
                </button>
              </li>
            ))}
          </ul>

          {kind !== "behaviors" && <ReseedNote />}
        </nav>

        <main className="device__screen">{children}</main>
      </div>
    </div>
  );
}
