import type { ReactNode, RefObject } from "react";
import type { KindKey } from "../types";
import { ReseedNote } from "./ReseedNote";
import "./device-frame.css";

const KIND_TABS: { key: KindKey; label: string }[] = [
  { key: "dex", label: "Dex" },
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
  editedOnly: boolean;
  onEditedOnly: (on: boolean) => void;
  readout: ReactNode;
  searchRef: RefObject<HTMLInputElement>;
  children: ReactNode;
};

/**
 * The handheld-style chrome: a device header with a segmented readout, a left
 * rail (search, the edited filter, the kind tabs), and the main screen. Search
 * and the filter only apply to the Dex; on the other kinds they recede.
 */
export function DeviceFrame({
  kind,
  onKind,
  query,
  onQuery,
  editedOnly,
  onEditedOnly,
  readout,
  searchRef,
  children,
}: Props) {
  const isDex = kind === "dex";
  return (
    <div className="device" id="app-shell">
      <header className="device__header">
        <div className="device__brand">
          <span className="device__lamp" aria-hidden="true" />
          <h1 className="device__title">
            chrooked<span className="device__title-dim">·pokedex</span>
          </h1>
        </div>
        <div className="device__readout mono" id="dex-summary">
          {readout}
        </div>
      </header>

      <div className="device__body">
        <nav className="device__rail" aria-label="Sections">
          <div className="device__search" data-disabled={!isDex}>
            <span className="device__search-key mono" aria-hidden="true">
              /
            </span>
            <input
              ref={searchRef}
              type="search"
              className="device__search-input"
              placeholder="Search dex"
              value={query}
              onChange={(event) => onQuery(event.target.value)}
              disabled={!isDex}
              aria-label="Search the dex by name"
            />
          </div>

          <button
            type="button"
            className="device__filter"
            data-on={editedOnly}
            aria-pressed={editedOnly}
            disabled={!isDex}
            onClick={() => onEditedOnly(!editedOnly)}
          >
            <span className="device__filter-lamp" aria-hidden="true" />
            Edited only
            <kbd className="device__kbd mono">E</kbd>
          </button>

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
