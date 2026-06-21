/* Thin adapters binding the api `/suggest/*` methods to the shape the generic
   ProposedColumn shell expects: `(id, direction) => Promise<SuggestResponse>`.
   Keeping these out of the shell keeps the shell section-agnostic. */

import { api } from "../../api";
import type { AbilityProposal, LearnsetProposal } from "../../types";

export function suggestAbilityCall(
  id: string,
  direction: string,
): Promise<AbilityProposal> {
  return api.suggestAbility(id, { direction });
}

export function suggestLearnsetCall(
  id: string,
  direction: string,
): Promise<LearnsetProposal> {
  return api.suggestLearnset(id, { direction, mode: "full" });
}
