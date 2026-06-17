/* A process-wide "the persisted dex data changed" signal.

   Each useResource instance holds its own fetch + cache, so a write made on one
   screen (e.g. editing a species' ability distribution from the Abilities page)
   only reloads that screen's copy. The dex page is fed by an always-mounted
   resource in App, which would otherwise stay stale until a full page reload.

   Mutations that change species data emit this event; the dex resource listens
   and refetches, so cross-screen writes are reflected without a manual reload.
   Mirrors the `chrooked:urlchange` pattern already used for URL state. */

const EVENT = "chrooked:datachange";

/** Signal that persisted dex data changed (call after a successful species write). */
export function emitDataChange(): void {
  window.dispatchEvent(new Event(EVENT));
}

/** Subscribe to data-change signals. Returns an unsubscribe function. */
export function onDataChange(handler: () => void): () => void {
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
