/* URL (de)serialization for the Team tab party. The party — up to six members,
   each a species chrooked_id and an optional matchup-altering ability — round-
   trips through the `team` query param so a built team is shareable and reload-
   safe, like every other view state. Percent-encoding is left to URLSearchParams
   (the same contract the dex filter codec uses), so the tokens stay readable.
   Pure, no React; unit-tested in teamViewCodec.test.ts. */

export interface PartyMember {
  id: string;
  ability: string | null;
}

/** Per the Decision Ledger: a team caps at six members. */
export const MAX_PARTY = 6;

/** Encode a party to a compact `team` value: members joined by ",", each token
    `id` or `id~ability`. chrooked_ids and ability names never contain "," or
    "~", so splitting is unambiguous; URLSearchParams owns percent-encoding of
    spaces and the rest. An empty party ⇒ "" (the writer drops the param). */
export function encodeParty(party: readonly PartyMember[]): string {
  return party
    .slice(0, MAX_PARTY)
    .map((member) => (member.ability ? `${member.id}~${member.ability}` : member.id))
    .join(",");
}

/** Swap the member at `slotIndex` for `incomingId` (fresh add — no ability yet),
    leaving every other slot untouched. Immutable: returns a new party. Out-of-range
    indices are a no-op copy. The full-team replace flow (ac10) routes both surfaces
    (Team picker + species detail) through this one helper so the swap stays uniform. */
export function replacePartyMember(
  party: readonly PartyMember[],
  slotIndex: number,
  incomingId: string,
): PartyMember[] {
  return party.map((member, i) =>
    i === slotIndex ? { id: incomingId, ability: null } : member,
  );
}

/** Decode the `team` value back to a party, dropping empty tokens and capping at
    six. A blank/absent value ⇒ empty party. Unknown ids are kept here (structure
    only); the tab drops any that don't resolve against the dex. */
export function decodeParty(raw: string | null): PartyMember[] {
  if (!raw) return [];
  const party: PartyMember[] = [];
  for (const token of raw.split(",")) {
    if (party.length >= MAX_PARTY) break;
    if (token === "") continue;
    const sep = token.indexOf("~");
    const id = sep === -1 ? token : token.slice(0, sep);
    const ability = sep === -1 ? null : token.slice(sep + 1) || null;
    if (id === "") continue;
    party.push({ id, ability });
  }
  return party;
}
