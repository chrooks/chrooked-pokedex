import "./status-view.css";

type ErrorProps = { message: string; status: number | null };

/**
 * The honest error state. When the base snapshot is missing the API returns 503
 * with the actionable "run snapshot" message; we surface it verbatim rather than
 * inventing our own copy.
 */
export function ErrorView({ message, status }: ErrorProps) {
  const isSnapshotMissing = status === 503;
  return (
    <div className="status-view status-view--error" role="alert" id="dex-error">
      <div className="status-view__badge mono">{status ?? "ERR"}</div>
      <p className="status-view__title">
        {isSnapshotMissing ? "Base snapshot not generated" : "Could not load data"}
      </p>
      <p className="status-view__detail">{message}</p>
      {isSnapshotMissing && (
        <code className="status-view__cmd mono">
          chrooked-pokedex snapshot --base &lt;path-to-1.11.2&gt;
        </code>
      )}
    </div>
  );
}

export function EmptyView({ message }: { message: string }) {
  // role="status" so filtering down to zero results is announced.
  return (
    <div className="status-view status-view--empty" role="status">
      <div className="status-view__badge mono" aria-hidden="true">
        ∅
      </div>
      <p className="status-view__detail">{message}</p>
    </div>
  );
}

/** A skeleton grid placeholder — no spinners (DESIGN.md). */
export function GridSkeleton({ count = 48 }: { count?: number }) {
  return (
    <div className="status-view__skeleton" aria-busy="true" aria-label="Loading dex">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="status-view__skeleton-cell" />
      ))}
    </div>
  );
}
