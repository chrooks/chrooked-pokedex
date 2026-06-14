/* A DATA-ONLY created ability rendered as a working link to its behavior packet.
   The packet markdown is fetched lazily on first expand (the report can carry
   many) and shown inline so the user never leaves the report. */

import { useState } from "react";
import { api, ApiError } from "../../api";
import type { DataOnlyEntry } from "../../types";

type Props = {
  entry: DataOnlyEntry;
};

export function PacketLink({ entry }: Props) {
  const [open, setOpen] = useState(false);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && markdown === null && !isLoading) {
      setIsLoading(true);
      setError(null);
      try {
        const packet = await api.packet(entry.packet_url);
        setMarkdown(packet.markdown);
      } catch (caught: unknown) {
        setError(
          caught instanceof ApiError
            ? caught.message
            : "Could not load the packet.",
        );
      } finally {
        setIsLoading(false);
      }
    }
  }

  const bodyId = `packet-body-${entry.chrooked_id}`;
  return (
    <li className="packet" id={`packet-${entry.chrooked_id}`}>
      <button
        type="button"
        className="packet__toggle"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => void toggle()}
      >
        <span className="packet__caret" aria-hidden="true">
          {open ? "▾" : "▸"}
        </span>
        <span className="packet__name mono">{entry.chrooked_id}</span>
        <span className="packet__symbol mono">{entry.symbol}</span>
        <span className="packet__tag">DATA-ONLY</span>
      </button>
      {open && (
        <div className="packet__body" id={bodyId}>
          {isLoading && <p className="packet__hint">Loading packet…</p>}
          {error !== null && <p className="packet__error">{error}</p>}
          {markdown !== null && (
            <pre className="packet__md mono">{markdown}</pre>
          )}
        </div>
      )}
    </li>
  );
}
