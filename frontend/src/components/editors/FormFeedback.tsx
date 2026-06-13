/* Shared write feedback: the loader's verbatim 422 message as an honest Error
   State, and the 409 delete-guard's citing-species list. Reused by every
   editor so the recovery copy stays consistent. */

type ErrorProps = {
  /** The server's verbatim message (loader 422 text, 503, etc.). */
  message: string;
  /** Species names blocking a delete (HTTP 409), shown as a recoverable list. */
  citing: string[] | null;
};

export function FormError({ message, citing }: ErrorProps) {
  if (citing !== null) {
    return (
      <div className="editor-error" role="alert">
        <span className="editor-error__label">Still in use</span>
        <p className="editor-error__message">
          Cited by {citing.join(", ")}. Deleting leaves those references
          dangling — confirm to delete anyway.
        </p>
      </div>
    );
  }
  return (
    <div className="editor-error" role="alert">
      <span className="editor-error__label">Rejected</span>
      <p className="editor-error__message">{message}</p>
    </div>
  );
}
