/* A failed preview/apply, rendered honestly: the status, the cause, and — when
   the server sent a structured RestoreError — the exact recovery command so a
   left-dirty fork is hand-recoverable. The dirty-tree (409) Error State with its
   Force toggle lives in PatchDrawer (it's coupled to the force/confirm flow);
   this renders every other failure. */

type Props = {
  status: number | null;
  message: string;
  /** The parsed `detail` body. A RestoreError carries `{ recovery, ... }`. */
  detail?: unknown;
};

export function ApplyErrorView({ status, message, detail }: Props) {
  const recovery = recoveryFrom(detail);
  return (
    <div className="apply-error apply-error--plain" id="apply-error" role="alert">
      <div className="apply-error__badge mono">{status ?? "ERR"}</div>
      <div className="apply-error__body">
        <p className="apply-error__title">Run failed</p>
        <p className="apply-error__detail">{message}</p>
        {recovery !== null && (
          <div className="apply-error__recovery">
            <p className="apply-error__recovery-label">Recover by hand:</p>
            <pre className="apply-error__recovery-cmd mono">{recovery}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

/** The recovery command from a structured error body, or null. */
function recoveryFrom(detail: unknown): string | null {
  if (detail !== null && typeof detail === "object" && "recovery" in detail) {
    const recovery = (detail as { recovery?: unknown }).recovery;
    return typeof recovery === "string" ? recovery : null;
  }
  return null;
}
