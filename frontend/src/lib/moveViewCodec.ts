/* The Moves binding of the generic view codec. Supplies the move valid-key sets
   (filter fields from the registry, sortable + hideable from the column
   registry). Pure, no React. */

import { MOVE_REGISTRY } from "./moveRegistry";
import { MOVE_COLUMNS } from "./moveColumns";
import { makeViewCodec } from "./viewCodec";

const FILTER_FIELDS = new Set(MOVE_REGISTRY.defs.map((def) => def.field));
const SORTABLE_KEYS = new Set<string>(
  MOVE_COLUMNS.filter((column) => column.sortable).map((column) => column.key),
);
const HIDEABLE_KEYS = new Set<string>(
  MOVE_COLUMNS.filter((column) => !column.locked).map((column) => column.key),
);

export const moveCodec = makeViewCodec({
  filterFields: FILTER_FIELDS,
  sortableKeys: SORTABLE_KEYS,
  hideableKeys: HIDEABLE_KEYS,
});
