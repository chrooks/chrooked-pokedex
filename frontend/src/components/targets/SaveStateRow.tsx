/* One line in the patch drawer for the state of the shared saves folder (#88).
 *
 * Calm technology: quiet when healthy, loud only when a human is actually
 * needed. Three registers, and nothing in between —
 *
 *   healthy      "Saves · newest from thor · synced 12m ago"   --text-dim, no frame
 *   unavailable  "Saves · sync status unavailable"             --text-faint, no frame
 *   attention    a framed banner naming the conflict files and their origin
 *                devices, or the device that fell behind while another played
 *
 * The unavailable case is deliberately NOT an error: Syncthing being down says
 * nothing about whether the saves are fine, so an error wall there would train
 * the eye to ignore the one state that matters.
 *
 * Both the row and its expansion are real <button>s. The D-pad drives DOM focus
 * (lib/spatialNav) and A clicks whatever it lands on, so being genuine controls
 * is the whole of the gamepad support — there is no pad-specific code here. */

import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import type { SaveStatus } from "../../types";
import "./save-state-row.css";

type Props = {
  targetId: string;
};

export function SaveStateRow({ targetId }: Props) {
  const [status, setStatus] = useState<SaveStatus | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [token, setToken] = useState(0);

  const recheck = useCallback(() => setToken((n) => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    api
      .targetSaveStatus(targetId, controller.signal)
      // A failed fetch is the same story as an unreachable Syncthing: nothing
      // to say, said quietly.
      .catch(() => ({ available: false, folder: "", conflicts: [] }) as SaveStatus)
      .then((next) => {
        if (!controller.signal.aborted) setStatus(next);
      });
    return () => controller.abort();
  }, [targetId, token]);

  const conflicts = status?.conflicts ?? [];
  const stale = status?.stale ?? [];
  const loud = conflicts.length > 0 || stale.length > 0;
  const tone = status === null ? "loading" : loud ? "loud" : status.available ? "calm" : "mute";

  return (
    <section
      className={`save-row save-row--${tone}`}
      id="save-state-row"
      aria-label="Save-state sync"
    >
      <button
        type="button"
        id="save-state-toggle"
        className="save-row__line"
        aria-expanded={expanded}
        aria-controls="save-state-detail"
        onClick={() => setExpanded((open) => !open)}
      >
        <span className="save-row__label mono">SAVES</span>
        <span className="save-row__summary">{summary(status, conflicts, stale)}</span>
        <span className="save-row__chevron mono" aria-hidden="true">
          {expanded ? "−" : "+"}
        </span>
      </button>

      {loud && (
        <div className="save-row__alert" id="save-state-alert" role="status">
          {conflicts.length > 0 ? (
            <ul className="save-row__conflicts">
              {conflicts.map((conflict) => (
                <li key={conflict.file}>
                  <span className="mono save-row__file">{conflict.file}</span>
                  <span className="save-row__from">
                    from {conflict.device ?? "an unknown device"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="save-row__stale">
              {stale.join(", ")} {stale.length === 1 ? "has" : "have"} not synced
              since {relative(status?.newest_seconds_ago)} — play there and the
              older save wins.
            </p>
          )}
        </div>
      )}

      {expanded && (
        <div className="save-row__detail" id="save-state-detail">
          {status?.available && status.devices?.length ? (
            <ul className="save-row__devices">
              {status.devices.map((device) => (
                <li key={device.id} className="save-row__device">
                  <span className="save-row__device-name mono">{device.name}</span>
                  <span className="save-row__device-seen">
                    {device.seconds_ago === null
                      ? "never seen"
                      : `synced ${relative(device.seconds_ago)}`}
                  </span>
                  <span className="save-row__device-pct mono">
                    {device.completion === null
                      ? "—"
                      : `${Math.round(device.completion)}%`}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="save-row__note">
              Syncthing did not answer on this machine. The saves on disk are
              untouched either way.
            </p>
          )}
          <button
            type="button"
            id="save-state-recheck"
            className="btn save-row__recheck"
            onClick={recheck}
          >
            Recheck
          </button>
        </div>
      )}
    </section>
  );
}

function summary(
  status: SaveStatus | null,
  conflicts: SaveStatus["conflicts"],
  stale: string[],
): string {
  if (status === null) return "checking…";
  if (conflicts.length > 0) {
    return conflicts.length === 1
      ? "1 conflicted save needs picking"
      : `${conflicts.length} conflicted saves need picking`;
  }
  if (stale.length > 0) return `${stale.join(", ")} behind`;
  if (!status.available) return "sync status unavailable";
  if (!status.newest) return "no device has synced yet";
  return `newest from ${status.newest} · synced ${relative(status.newest_seconds_ago)}`;
}

/** Coarse on purpose — "12m ago" is the useful precision for a save file. */
function relative(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "at an unknown time";
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}
