/* "New types only": the pool filter that hides every species already sharing a
   type with the team. Building a type-diverse team otherwise means hand-adding
   a `Type is not X` pill per type the party covers, which is exactly the tedium
   this collapses into one toggle. Pure, no React. */

import { typeSlug } from "./format";

/** Every type the party covers, slugged for comparison. */
export function teamTypeSet(
  members: readonly { types: readonly string[] }[],
): Set<string> {
  const covered = new Set<string>();
  for (const member of members) {
    for (const type of member.types) covered.add(typeSlug(type));
  }
  return covered;
}

/** True when NONE of `types` is already on the team — i.e. this species brings
    a type the party does not have. A dual-type sharing even one type is out:
    the point is a party with no overlap at all. An empty team covers nothing,
    so every species is new. */
export function bringsNewType(
  types: readonly string[],
  covered: ReadonlySet<string>,
): boolean {
  return !types.some((type) => covered.has(typeSlug(type)));
}
