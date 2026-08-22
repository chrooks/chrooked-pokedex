import type { SyncOutcome } from "../../types";
import "./sync-status.css";

interface Props {
  sync: SyncOutcome;
  /** Distinguishes the two mount points so ids stay unique on one page. */
  idPrefix?: string;
}

/** Where an apply's files went after they were written.
 *
 * A failure here is NOT an apply failure — the files on this machine are valid
 * either way — so the failed state is a warning, never an error. The server
 * writes `detail` to name the fix ("open Termux and run: sshd"), so it is shown
 * verbatim rather than being re-worded here. */
export function SyncStatus({ sync, idPrefix = "patch" }: Props) {
  return (
    <div className="sync-status" id={`${idPrefix}-sync-status`}>
      <SyncLine sync={sync} label="handheld" />
      {sync.save_backup && (
        <SyncLine
          sync={sync.save_backup}
          label="saves"
          id={`${idPrefix}-sync-save-backup`}
        />
      )}
    </div>
  );
}

function SyncLine({
  sync,
  label,
  id,
}: {
  sync: SyncOutcome;
  label: string;
  id?: string;
}) {
  const stats = [
    sync.files !== undefined ? `${sync.files} file${sync.files === 1 ? "" : "s"}` : null,
    sync.seconds !== undefined ? `${sync.seconds}s` : null,
  ].filter(Boolean);

  return (
    <p
      className={`sync-status__line sync-status__line--${sync.ok ? "ok" : "warn"}`}
      id={id}
    >
      <span className="sync-status__mark mono" aria-hidden="true">
        {sync.ok ? "✓" : "⚠"}
      </span>
      <span className="sync-status__label mono">{label}</span>
      <span className="sync-status__detail">{sync.detail}</span>
      {stats.length > 0 && (
        <span className="sync-status__stats mono">{stats.join(" · ")}</span>
      )}
    </p>
  );
}
