/* A monotonic session-local id for repeatable editor rows. React keys on
   removable/reorderable lists must be stable per row (not the array index), or
   removing a middle row reattaches DOM/focus state to the wrong row. A simple
   incrementing counter is enough — ids only need to be unique within a session,
   never persisted. */

let counter = 0;

export function rowId(): number {
  counter += 1;
  return counter;
}
