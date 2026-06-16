/* The Abilities binding of the generic view codec. Abilities have no columns
   (def-list), so the hideable set is empty; sortable keys are name + edited.
   Pure, no React. */

import { ABILITY_REGISTRY, ABILITY_SORTABLE } from "./abilityRegistry";
import { makeViewCodec } from "./viewCodec";

const FILTER_FIELDS = new Set(ABILITY_REGISTRY.defs.map((def) => def.field));
const SORTABLE_KEYS = new Set<string>(ABILITY_SORTABLE.map((c) => c.key));
const HIDEABLE_KEYS = new Set<string>();

export const abilityCodec = makeViewCodec({
  filterFields: FILTER_FIELDS,
  sortableKeys: SORTABLE_KEYS,
  hideableKeys: HIDEABLE_KEYS,
});
