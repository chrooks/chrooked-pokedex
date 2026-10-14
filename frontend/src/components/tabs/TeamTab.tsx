import { useMemo, useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useUrlState } from "../../hooks/useUrlState";
import { useEntityView, type EntityParamKeys } from "../../hooks/useEntityView";
import { DEX_REGISTRY, appendAnswerFilter, evalEntries, matchesQuery } from "../../lib/dexFilters";
import { uid } from "../../lib/uid";
import { dexCodec } from "../../lib/dexViewCodec";
import { cellMap } from "../../lib/typeChartGrid";
import { teamMatchups, type TeamMember } from "../../lib/teamMatchups";
import { effectiveTypes } from "../../lib/abilityTypeModifiers";
import { bringsNewType, teamTypeSet } from "../../lib/teamTypeGap";
import {
  decodeParty,
  encodeParty,
  MAX_PARTY,
  replacePartyMember,
} from "../../lib/teamViewCodec";
import type { DexEntry, TypeChartCell } from "../../types";
import { PokeballSpinner } from "../PokeballSpinner";
import { ErrorView } from "../StatusView";
import { EntityControls } from "../filters/EntityControls";
import { PartyPicker } from "../team/PartyPicker";
import { PartyPool } from "../team/PartyPool";
import { PartySlot } from "../team/PartySlot";
import { SavedTeamsMenu } from "../team/SavedTeamsMenu";
import { HolesPanel } from "../team/HolesPanel";
import { candidateMember, teamFit, teamHoles, type Fit } from "../../lib/teamFit";
import { bst } from "../../lib/format";
import { WhyPanel } from "../team/WhyPanel";
import { MatchupTable } from "../team/MatchupTable";
import { ReplaceDialog } from "../team/ReplaceDialog";
import "./tabs.css";
import "../team/team-tab.css";

type Resolved = { entry: DexEntry; ability: string | null; partyIndex: number };

/** Redux mode: every distinct ability the mon has, all treated as active. */
function allAbilities(entry: DexEntry): string[] {
  const { primary, secondary, hidden } = entry.abilities;
  return [...new Set([primary, secondary, hidden].filter((a): a is string => !!a))];
}

/** The Team pool owns its own namespaced filter params so a pill set here never
    bleeds into the Species tab's `filter` (the same D3 rule Moves/Abilities
    follow). Sort and columns stay unused — the pool is one dex-ordered line. */
const TEAM_PARAM_KEYS: EntityParamKeys = {
  filter: "tfilter",
  sort: "tsort",
  hide: "thide",
};

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
  const [controls, setControls] = useEntityView(dexCodec, TEAM_PARAM_KEYS);
  const party = view.party;
  const backdrop = view.backdrop;
  const poolQuery = view.poolQuery;
  const newTypesOnly = view.poolNewTypes;
  const redux = view.teamRedux;
  const offenseOpen = view.teamOffense;
  const suggest = view.teamSuggest;
  // The pool card under the pointer/focus — feeds the Why panel.
  const [pointedId, setPointedId] = useState<string | null>(null);
  // The fresh species awaiting a swap decision — set when a pick lands on a full
  // team, cleared when the replace dialog resolves or is dismissed (ac10).
  const [replaceIncoming, setReplaceIncoming] = useState<DexEntry | null>(null);
  // Clear-team arms on the first click and fires on the second (the SavedTeams
  // delete pattern) — leaving the button disarms it.
  const [confirmingClear, setConfirmingClear] = useState(false);

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

  const chartByKey = useMemo(() => (cells.length ? cellMap(cells) : null), [cells]);

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

  // Every type the party already covers — the "New types only" toggle reads it.
  // A member's chosen type-adding ability counts (Phantom Rotom covers Ghost).
  const coveredTypes = useMemo(
    () =>
      teamTypeSet(
        resolved.map((r) => ({
          types: effectiveTypes(r.entry.types, redux ? allAbilities(r.entry) : r.ability),
        })),
      ),
    [resolved, redux],
  );

  // The pool: the whole dex narrowed by the search text and the filter pills —
  // the SAME predicates the Species tab runs, so a `Type weak to Fire` pill
  // means here exactly what it means there. The chart map feeds the matchup
  // operators; without it those pills would silently match nothing. The
  // new-types pass runs last, over whatever the other two left.
  const pool = useMemo(() => {
    let list: readonly DexEntry[] = entries;
    const query = poolQuery.trim().toLowerCase();
    if (query) list = list.filter((entry) => matchesQuery(entry, query));
    if (controls.filter.length) {
      list = list.filter((entry) => evalEntries(entry, controls.filter, chartByKey));
    }
    if (newTypesOnly) {
      list = list.filter((entry) => bringsNewType(entry.types, coveredTypes));
    }
    return list;
  }, [entries, poolQuery, controls.filter, chartByKey, newTypesOnly, coveredTypes]);

  const members = useMemo<TeamMember[]>(
    () =>
      resolved.map((r) => ({
        id: r.entry.chrooked_id,
        name: r.entry.name,
        types: r.entry.types,
        ability: redux ? allAbilities(r.entry) : r.ability,
      })),
    [resolved, redux],
  );
  const columns = useMemo(() => resolved.map((r) => ({ entry: r.entry })), [resolved]);
  const matchups = useMemo(() => teamMatchups(members, cells), [members, cells]);
  const holes = useMemo(() => teamHoles(matchups.defense), [matchups]);

  const partyIds = useMemo(() => new Set(party.map((m) => m.id)), [party]);

  // Suggest mode: score every pool species against the team (Defense-first,
  // lib/teamFit), then sort the pool by it — highest score, then BST, then dex
  // order; species already on the team sink to the end. Off, or with an empty
  // party, the pool keeps dex order and no fit is computed.
  const isSuggesting = suggest && members.length > 0 && chartByKey !== null;
  const fits = useMemo<Map<string, Fit> | null>(() => {
    if (!isSuggesting || chartByKey === null) return null;
    const out = new Map<string, Fit>();
    for (const entry of pool) {
      out.set(entry.chrooked_id, teamFit(matchups, candidateMember(entry, redux), chartByKey));
    }
    return out;
  }, [isSuggesting, pool, matchups, redux, chartByKey]);
  const shownPool = useMemo(() => {
    if (fits === null) return pool;
    const rank = (entry: DexEntry) => (partyIds.has(entry.chrooked_id) ? -Infinity : fits.get(entry.chrooked_id)?.score ?? 0);
    return [...pool].sort(
      (a, b) =>
        rank(b) - rank(a) ||
        (bst(b.stats) ?? 0) - (bst(a.stats) ?? 0) ||
        (a.dex ?? 0) - (b.dex ?? 0),
    );
  }, [pool, fits, partyIds]);
  const pointedEntry = pointedId ? byId.get(pointedId) ?? null : null;
  const pointedFit = pointedId && fits ? fits.get(pointedId) ?? null : null;

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
  function openProfile(id: string) {
    // Selection only — the ledger opens as a panel OVER the Team tab, so the
    // team you are building stays on screen behind it. Closing returns you to
    // the party, not to the dex.
    update({ selected: id });
  }
  function clearTeam() {
    if (!confirmingClear) {
      setConfirmingClear(true);
      return;
    }
    setConfirmingClear(false);
    update({ party: [] });
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
        <h2 className="team__heading">Team builder</h2>
        <span className="team__count mono" data-full={full}>
          {resolved.length}/{MAX_PARTY}
        </span>
        <div className="team__toolbar-actions">
          <SavedTeamsMenu
            encodedParty={encodeParty(party)}
            canSave={party.length > 0}
            onLoad={(encoded) => update({ party: decodeParty(encoded) })}
          />
          {party.length > 0 && (
            <button
              type="button"
              id="team-clear"
              className="saved-teams__btn saved-teams__btn--danger team__clear"
              data-confirming={confirmingClear}
              aria-label={
                confirmingClear
                  ? "Confirm: remove every team member"
                  : "Remove every team member"
              }
              onClick={clearTeam}
              onBlur={() => setConfirmingClear(false)}
              onMouseLeave={() => setConfirmingClear(false)}
            >
              {confirmingClear ? "Confirm?" : "Clear"}
            </button>
          )}
          {resolved.length > 0 && (
            <button
              type="button"
              id="team-redux"
              className="team__new-types"
              data-on={redux}
              aria-pressed={redux}
              title="Treat every ability each member has as active at once, so all its immunities, resists, and weaknesses show together"
              onClick={() => update({ teamRedux: !redux })}
            >
              Redux mode
            </button>
          )}
          {resolved.length > 0 && (
            <button
              type="button"
              id="team-suggest"
              className="team__new-types"
              data-on={suggest}
              aria-pressed={suggest}
              title="Sort the pool by how much each species shores up this team's defense, with the reasons on each card"
              onClick={() => update({ teamSuggest: !suggest })}
            >
              Suggest
            </button>
          )}
        </div>
      </div>

      <section className="team__main" aria-label="Species pool">
        <div className="team__pool-search" id="team-pool-search">
          <PartyPicker
            query={poolQuery}
            onQuery={(next) => update({ poolQuery: next })}
            resultCount={pool.length}
            onSubmit={() => {
              const first = shownPool.find((entry) => !partyIds.has(entry.chrooked_id));
              if (first) addMember(first.chrooked_id);
            }}
          />
          {resolved.length > 0 && (
            <button
              type="button"
              id="team-new-types"
              className="team__new-types"
              data-on={newTypesOnly}
              aria-pressed={newTypesOnly}
              title={`Hide every species sharing a type with the team (${[...coveredTypes].length} covered)`}
              onClick={() => update({ poolNewTypes: !newTypesOnly })}
            >
              New types only
            </button>
          )}
        </div>

        <EntityControls
          idPrefix="teamc"
          ariaLabel="Species pool filters"
          defs={DEX_REGISTRY.defs}
          sortable={[]}
          columns={[]}
          filter={controls.filter}
          sort={controls.sort}
          hidden={controls.hidden}
          onChange={setControls}
        />

        {pool.length === 0 ? (
          <p className="team__pool-empty" id="party-pool-empty">
            {newTypesOnly
              ? "No species left that avoids every type your team already covers."
              : "No species match this search."}
          </p>
        ) : (
          <>
            {fits !== null && (
              <p className="team__sort-note" id="team-sort-note">
                Sorted by fit for this team, within your filters
                {redux ? " · all abilities count" : " · base typing (Redux mode counts every ability)"}
              </p>
            )}
            <PartyPool
              entries={shownPool}
              partyIds={partyIds}
              onAdd={addMember}
              backdropTargetId={backdrop}
              fits={fits}
              onPoint={fits ? setPointedId : undefined}
            />
          </>
        )}
      </section>

      <aside className="team__side" aria-label="Your team">
        {resolved.length === 0 ? (
          <div className="team__empty" id="team-empty">
            <div className="team__empty-mark" aria-hidden="true">
              <span className="team__empty-slot" />
              <span className="team__empty-slot" />
              <span className="team__empty-slot" />
            </div>
            <h3 className="team__empty-title">Start building your team</h3>
            <p className="team__empty-body">
              Pick up to six Pokémon from the pool. Their combined type matchups — everything
              that threatens the team and everything it covers — build here as you go.
            </p>
          </div>
        ) : (
          <>
            <ul className="team__party" id="team-party">
              {resolved.map((r) => (
                <PartySlot
                  key={r.partyIndex}
                  entry={r.entry}
                  ability={r.ability}
                  index={r.partyIndex}
                  onRemove={() => removeMember(r.partyIndex)}
                  onAbility={(ability) => setAbility(r.partyIndex, ability)}
                  onOpen={() => openProfile(r.entry.chrooked_id)}
                  backdropTargetId={backdrop}
                />
              ))}
            </ul>
            <div className="team__inspector" data-split={fits !== null}>
              <HolesPanel holes={holes} memberNames={members.map((m) => m.name)} />
              {fits !== null && <WhyPanel entry={pointedEntry} fit={pointedFit} />}
            </div>
            <MatchupTable
              id="team-defense"
              variant="defense"
              title="Defensive Matchups"
              subtitle="How hard each attacking type hits your team · click a weak cell to find an answer"
              columns={columns}
              rows={matchups.defense}
              backdropTargetId={backdrop}
              onWeakClick={(type) =>
                setControls({ filter: appendAnswerFilter(controls.filter, type, uid) })
              }
            />
            <section className="team__offense" aria-labelledby="team-offense-toggle">
              <button
                type="button"
                id="team-offense-toggle"
                className="team__disclosure"
                aria-expanded={offenseOpen}
                aria-controls="team-offense"
                onClick={() => update({ teamOffense: !offenseOpen })}
              >
                <span className="team__disclosure-caret" aria-hidden="true">
                  {offenseOpen ? "▾" : "▸"}
                </span>
                Offensive Coverage
              </button>
              {offenseOpen && (
                <MatchupTable
                  id="team-offense"
                  variant="offense"
                  title="Offensive Coverage"
                  subtitle="Best STAB each member lands on every defending type"
                  columns={columns}
                  rows={matchups.offense}
                  backdropTargetId={backdrop}
                  hideHeader
                />
              )}
            </section>
          </>
        )}
      </aside>

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
