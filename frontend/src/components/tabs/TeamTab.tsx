import { useMemo, useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useUrlState } from "../../hooks/useUrlState";
import { teamMatchups, type TeamMember } from "../../lib/teamMatchups";
import {
  decodeParty,
  encodeParty,
  MAX_PARTY,
  replacePartyMember,
} from "../../lib/teamViewCodec";
import type { DexEntry, TypeChartCell } from "../../types";
import { PokeballSpinner } from "../PokeballSpinner";
import { ErrorView } from "../StatusView";
import { PartyPicker } from "../team/PartyPicker";
import { PartySlot } from "../team/PartySlot";
import { SavedTeams } from "../team/SavedTeams";
import { MatchupTable } from "../team/MatchupTable";
import { ReplaceDialog } from "../team/ReplaceDialog";
import "./tabs.css";
import "../team/team-tab.css";

type Resolved = { entry: DexEntry; ability: string | null; partyIndex: number };

/**
 * The Team tab: build a party of up to six species and read its type coverage
 * two ways — a Defensive Matchups grid (what hits the team, and how hard) and an
 * Offensive Coverage grid (what the team hits back). Both are powered by OUR
 * merged type chart (base ⊕ Ruleset) and honor the active backdrop, so a fork's
 * edited chart swaps straight in. The party lives in the URL, so a team is
 * shareable and survives a reload like every other view state.
 */
export function TeamTab() {
  const [view, update] = useUrlState();
  const party = view.party;
  const backdrop = view.backdrop;
  // The fresh species awaiting a swap decision — set when a pick lands on a full
  // team, cleared when the replace dialog resolves or is dismissed (ac10).
  const [replaceIncoming, setReplaceIncoming] = useState<DexEntry | null>(null);

  // Backdrop-aware fetchers, memoized by backdrop id so useResource sees a stable
  // reference and refetches only when the fork flips (same pattern as TypeChartTab).
  const dexFetcher = useMemo(
    () => (backdrop ? api.targetDex(backdrop) : api.dex),
    [backdrop],
  );
  const chartFetcher = useMemo(
    () => (backdrop ? api.targetTypeChart(backdrop) : api.typeChart),
    [backdrop],
  );
  const dex = useResource<DexEntry[]>(dexFetcher);
  const chart = useResource<TypeChartCell[]>(chartFetcher);

  const entries = useMemo(() => dex.data ?? [], [dex.data]);
  const cells = useMemo(() => chart.data ?? [], [chart.data]);

  const byId = useMemo(() => {
    const map = new Map<string, DexEntry>();
    for (const entry of entries) map.set(entry.chrooked_id, entry);
    return map;
  }, [entries]);

  // Resolve the URL party against the dex, preserving each member's party index
  // so remove/ability edits target the right slot even if an id fails to resolve.
  const resolved = useMemo<Resolved[]>(() => {
    const out: Resolved[] = [];
    party.forEach((member, partyIndex) => {
      const entry = byId.get(member.id);
      if (entry) out.push({ entry, ability: member.ability, partyIndex });
    });
    return out;
  }, [party, byId]);

  const members = useMemo<TeamMember[]>(
    () =>
      resolved.map((r) => ({
        id: r.entry.chrooked_id,
        name: r.entry.name,
        types: r.entry.types,
        ability: r.ability,
      })),
    [resolved],
  );
  const columns = useMemo(() => resolved.map((r) => ({ entry: r.entry })), [resolved]);
  const matchups = useMemo(() => teamMatchups(members, cells), [members, cells]);

  const partyIds = useMemo(() => new Set(party.map((m) => m.id)), [party]);

  function addMember(id: string) {
    if (partyIds.has(id)) return; // no duplicates (the picker also guards this)
    if (party.length < MAX_PARTY) {
      update({ party: [...party, { id, ability: null }] });
      return;
    }
    // Full team + fresh species: don't dead-end — open the replace dialog (ac10).
    const entry = byId.get(id);
    if (entry) setReplaceIncoming(entry);
  }

  function replaceMember(partyIndex: number) {
    if (replaceIncoming === null) return;
    update({ party: replacePartyMember(party, partyIndex, replaceIncoming.chrooked_id) });
    setReplaceIncoming(null);
  }
  function removeMember(partyIndex: number) {
    update({ party: party.filter((_, i) => i !== partyIndex) });
  }
  function setAbility(partyIndex: number, ability: string | null) {
    update({
      party: party.map((member, i) => (i === partyIndex ? { ...member, ability } : member)),
    });
  }

  if (dex.error !== null) return <ErrorView message={dex.error} status={dex.status} />;
  if (chart.error !== null) return <ErrorView message={chart.error} status={chart.status} />;
  if (dex.isLoading || chart.isLoading) {
    return (
      <div className="tab-loading">
        <PokeballSpinner label="Loading team builder…" />
      </div>
    );
  }

  const full = party.length >= MAX_PARTY;

  return (
    <div className="tab tab--team" id="tab-team">
      <div className="team__toolbar">
        <div className="team__toolbar-title">
          <h2 className="team__heading">Team builder</h2>
          <span className="team__count mono" data-full={full}>
            {resolved.length}/{MAX_PARTY}
          </span>
        </div>
        <p className="team__hint">
          Add species to see how the team stands up defensively and what it covers on offense.
        </p>
      </div>

      <PartyPicker
        entries={entries}
        partyIds={partyIds}
        onAdd={addMember}
        backdropTargetId={backdrop}
      />

      <SavedTeams
        encodedParty={encodeParty(party)}
        canSave={party.length > 0}
        onLoad={(encoded) => update({ party: decodeParty(encoded) })}
      />

      {resolved.length > 0 && (
        <ul className="team__party" id="team-party">
          {resolved.map((r) => (
            <PartySlot
              key={r.partyIndex}
              entry={r.entry}
              ability={r.ability}
              index={r.partyIndex}
              onRemove={() => removeMember(r.partyIndex)}
              onAbility={(ability) => setAbility(r.partyIndex, ability)}
              backdropTargetId={backdrop}
            />
          ))}
        </ul>
      )}

      {resolved.length === 0 ? (
        <div className="team__empty" id="team-empty">
          <div className="team__empty-mark" aria-hidden="true">
            <span className="team__empty-slot" />
            <span className="team__empty-slot" />
            <span className="team__empty-slot" />
          </div>
          <h3 className="team__empty-title">Start building your team</h3>
          <p className="team__empty-body">
            Search above and add up to six Pokémon. Their combined type matchups — everything
            that threatens the team and everything it covers — build here as you go.
          </p>
        </div>
      ) : (
        <div className="team__tables">
          <MatchupTable
            id="team-defense"
            variant="defense"
            title="Defensive Matchups"
            subtitle="How hard each attacking type hits your team"
            columns={columns}
            rows={matchups.defense}
            backdropTargetId={backdrop}
          />
          <MatchupTable
            id="team-offense"
            variant="offense"
            title="Offensive Coverage"
            subtitle="Best STAB each member lands on every defending type"
            columns={columns}
            rows={matchups.offense}
            backdropTargetId={backdrop}
          />
        </div>
      )}

      {replaceIncoming !== null && (
        <ReplaceDialog
          incoming={replaceIncoming}
          members={resolved.map((r) => ({ partyIndex: r.partyIndex, entry: r.entry }))}
          onReplace={replaceMember}
          onClose={() => setReplaceIncoming(null)}
          backdropTargetId={backdrop}
        />
      )}
    </div>
  );
}
