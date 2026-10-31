import { useEffect, useMemo, useState } from "react";
import { api, getJson } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useUrlState } from "../../hooks/useUrlState";
import { cellMap } from "../../lib/typeChartGrid";
import { memberDefense, multBucket, multGlyph, type TeamMember } from "../../lib/teamMatchups";
import type { DexEntry, Move, Target, TypeChartCell } from "../../types";
import { DexSprite } from "../DexSprite";
import { PokeballSpinner } from "../PokeballSpinner";
import { TypeChip } from "../TypeChip";
import "./tabs.css";
import "./companion.css";

/**
 * The companion screen: the handheld's bottom display while a Target runs on
 * the top one. Reads what `chrooked_zz_companion.rb` pushes — the party, and
 * in battle the foes — and lays the matchups beside it, so the answer to "what
 * do I click" is on the second screen, not in a wiki tab.
 *
 * Touch-only by design: on the handheld the controller follows the active
 * screen, so this view never claims the gamepad.
 */

const POLL_MS = 2000;
/** Past this the game is probably closed or the mod is off; say so. */
const STALE_S = 600;

interface LiveMove {
  id: string;
  pp: number;
  totalpp: number;
}

interface LiveMon {
  id: string;
  base_id: string;
  species?: string;
  name?: string;
  level?: number;
  hp?: number;
  totalhp?: number;
  status?: string | null;
  ability?: string | null;
  item?: string | null;
  types?: string[];
  moves?: LiveMove[];
  active?: boolean;
  egg?: boolean;
}

interface LiveState {
  available: boolean;
  engine: string;
  seq?: number;
  age_s?: number;
  scene?: string;
  map?: string | null;
  party?: LiveMon[];
  foes?: LiveMon[];
  wild?: boolean;
  trainer?: string | null;
}

const LIVE_ENGINES = new Set(["rejuv", "essentials"]);

/** Engine symbols arrive as `DRACOMETEOR`; dex ids are `dracometeor`. */
function key(value: string | null | undefined): string {
  return (value ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function useLive(engine: string | null): LiveState | null {
  const [live, setLive] = useState<LiveState | null>(null);
  useEffect(() => {
    if (!engine) return;
    let stopped = false;
    const controller = new AbortController();
    const tick = async () => {
      try {
        const next = await getJson<LiveState>(`/api/live/${engine}`, controller.signal);
        if (!stopped) setLive(next);
      } catch {
        // A missed poll keeps the last state on screen; the next one retries.
      }
    };
    void tick();
    const timer = setInterval(() => void tick(), POLL_MS);
    return () => {
      stopped = true;
      controller.abort();
      clearInterval(timer);
    };
  }, [engine]);
  return live;
}

/** The live ability name as the dex spells it, or null when the dex lacks it
    (a non-type-altering ability contributes nothing to a matchup anyway). */
function matchAbility(live: string | null | undefined, entry: DexEntry | undefined): string | null {
  if (!live || !entry) return null;
  const want = key(live);
  const { primary, secondary, hidden } = entry.abilities;
  return [primary, secondary, hidden].find((name) => name && key(name) === want) ?? null;
}

function toMember(
  mon: LiveMon,
  entry: DexEntry | undefined,
  canonType: (t: string) => string,
): TeamMember | null {
  const types = mon.types?.length ? mon.types.map(canonType) : (entry?.types ?? []);
  if (types.length === 0) return null;
  return {
    id: mon.id,
    name: mon.name ?? entry?.name ?? mon.species ?? "?",
    types,
    ability: matchAbility(mon.ability, entry),
  };
}

/** Worst case for `me`: the foe's best STAB type into my typing. */
function defenseAgainst(
  me: TeamMember,
  foe: TeamMember,
  byKey: ReadonlyMap<string, TypeChartCell>,
): number | null {
  let worst: number | null = null;
  for (const type of foe.types) {
    const mult = memberDefense(me, type, byKey);
    if (mult !== null) worst = worst === null ? mult : Math.max(worst, mult);
  }
  return worst;
}

function Glyph({ mult }: { mult: number | null }) {
  if (mult === null) return <span className="companion__glyph" data-bucket="none">·</span>;
  const glyph = multGlyph(mult) || "1";
  return (
    <span className="companion__glyph" data-bucket={multBucket(mult)}>
      {glyph}
      <span className="companion__glyph-x">×</span>
    </span>
  );
}

function HpBar({ hp, totalhp }: { hp?: number; totalhp?: number }) {
  if (!totalhp) return null;
  const pct = Math.max(0, Math.min(100, Math.round(((hp ?? 0) / totalhp) * 100)));
  const zone = pct > 50 ? "ok" : pct > 20 ? "low" : "crit";
  return (
    <div className="companion__hp" role="meter" aria-valuenow={hp} aria-valuemax={totalhp} aria-label="HP">
      <div className="companion__hp-fill" data-zone={zone} style={{ width: `${pct}%` }} />
      <span className="companion__hp-text">
        {hp}/{totalhp}
      </span>
    </div>
  );
}

type MonCardProps = {
  mon: LiveMon;
  entry: DexEntry | undefined;
  member: TeamMember | null;
  backdropTargetId: string;
  children?: React.ReactNode;
};

function MonCard({ mon, entry, member, backdropTargetId, children }: MonCardProps) {
  if (mon.egg) {
    return (
      <div className="companion__mon companion__mon--egg">
        <span className="companion__name">Egg</span>
      </div>
    );
  }
  return (
    <div className="companion__mon" data-active={mon.active ? "true" : undefined} data-fainted={mon.hp === 0 ? "true" : undefined}>
      <DexSprite
        chrookedId={entry?.chrooked_id ?? mon.base_id}
        dex={entry?.dex ?? null}
        name={member?.name ?? mon.name ?? "?"}
        backdropTargetId={backdropTargetId}
        size={56}
      />
      <div className="companion__mon-body">
        <div className="companion__mon-head">
          <span className="companion__name">{mon.name ?? entry?.name ?? mon.species}</span>
          {mon.level !== undefined && <span className="companion__level">Lv {mon.level}</span>}
          {mon.status && <span className="companion__status">{mon.status}</span>}
        </div>
        <HpBar hp={mon.hp} totalhp={mon.totalhp} />
        <div className="companion__chips">
          {(member?.types ?? []).map((type) => (
            <TypeChip key={type} type={type} variant="code" />
          ))}
          {mon.ability && <span className="companion__ability">{matchAbility(mon.ability, entry) ?? mon.ability}</span>}
          {mon.item && <span className="companion__item">{mon.item}</span>}
        </div>
        {children}
      </div>
    </div>
  );
}

export function CompanionTab() {
  const [view] = useUrlState();
  const targets = useResource<Target[]>(api.targets);
  const target = useMemo(() => {
    const all = targets.data ?? [];
    return (
      all.find((t) => t.id === view.backdrop && LIVE_ENGINES.has(t.engine)) ??
      all.find((t) => LIVE_ENGINES.has(t.engine)) ??
      null
    );
  }, [targets.data, view.backdrop]);
  const targetId = target?.id ?? null;
  const engine = target?.engine ?? null;

  const dexFetcher = useMemo(() => (targetId ? api.targetDex(targetId) : api.dex), [targetId]);
  const chartFetcher = useMemo(() => (targetId ? api.targetTypeChart(targetId) : api.typeChart), [targetId]);
  const movesFetcher = useMemo(() => (targetId ? api.targetMoves(targetId) : api.moves), [targetId]);
  const dex = useResource<DexEntry[]>(dexFetcher);
  const chart = useResource<TypeChartCell[]>(chartFetcher);
  const moves = useResource<Move[]>(movesFetcher);
  const live = useLive(engine);

  const byId = useMemo(() => new Map((dex.data ?? []).map((e) => [e.chrooked_id, e])), [dex.data]);
  const byKey = useMemo(() => cellMap(chart.data ?? []), [chart.data]);
  const moveByKey = useMemo(() => new Map((moves.data ?? []).map((m) => [key(m.name), m])), [moves.data]);
  const typeByKey = useMemo(() => {
    const map = new Map<string, string>();
    for (const cell of chart.data ?? []) {
      map.set(key(cell.attacker), cell.attacker);
      map.set(key(cell.defender), cell.defender);
    }
    return map;
  }, [chart.data]);
  const canonType = (type: string) => typeByKey.get(key(type)) ?? type;
  const lookup = (mon: LiveMon) => byId.get(mon.id) ?? byId.get(mon.base_id);

  if (targets.isLoading || dex.isLoading || chart.isLoading) {
    return (
      <div className="tab tab-loading">
        <PokeballSpinner label="Loading the dex" />
      </div>
    );
  }
  if (!target) {
    return (
      <div className="tab companion companion--empty">
        <p>No Rejuvenation or Essentials Target is registered. Add one on the Targets tab, then open this screen on the handheld.</p>
      </div>
    );
  }
  if (!live || !live.available) {
    return (
      <div className="tab companion companion--empty">
        <p className="companion__title">{target.label}</p>
        <p>Waiting for the game. Start a battle or change maps and the party appears here.</p>
      </div>
    );
  }

  const foes = (live.foes ?? []).map((mon) => ({ mon, entry: lookup(mon), member: null as TeamMember | null }));
  for (const foe of foes) foe.member = toMember(foe.mon, foe.entry, canonType);
  const inBattle = live.scene === "battle" && foes.length > 0;
  const stale = (live.age_s ?? 0) > STALE_S;

  return (
    <div className="tab companion" data-stale={stale ? "true" : undefined}>
      <header className="companion__bar">
        <span className="companion__title">{target.label}</span>
        <span className="companion__where">
          {inBattle ? (live.wild ? "Wild battle" : `vs ${live.trainer ?? "trainer"}`) : (live.map ?? "Overworld")}
        </span>
        <span className="companion__age">{stale ? `last seen ${Math.round((live.age_s ?? 0) / 60)} min ago` : `${live.age_s ?? 0}s ago`}</span>
      </header>

      {inBattle && (
        <section className="companion__foes" aria-label="Opponents">
          {foes.map(({ mon, entry, member }, i) => (
            <MonCard key={`${mon.id}-${i}`} mon={mon} entry={entry} member={member} backdropTargetId={target.id} />
          ))}
        </section>
      )}

      <section className="companion__party" aria-label="Party">
        {(live.party ?? []).map((mon, i) => {
          const entry = lookup(mon);
          const member = toMember(mon, entry, canonType);
          return (
            <MonCard key={`${mon.id}-${i}`} mon={mon} entry={entry} member={member} backdropTargetId={target.id}>
              {inBattle && member && (
                <div className="companion__vs">
                  {foes.map((foe, j) => (
                    <span key={j} className="companion__vs-cell" title={`${foe.member?.name ?? "foe"} hits ${member.name}`}>
                      <span className="companion__vs-label">takes</span>
                      <Glyph mult={foe.member ? defenseAgainst(member, foe.member, byKey) : null} />
                    </span>
                  ))}
                </div>
              )}
              {!mon.egg && (
                <ul className="companion__moves">
                  {(mon.moves ?? []).map((lm, k) => {
                    const move = moveByKey.get(key(lm.id));
                    const type = move ? canonType(move.type) : null;
                    return (
                      <li key={k} className="companion__move" data-type={type ? key(type) : undefined} style={type ? ({ "--chip": `var(--type-${key(type)}, var(--text-dim))` } as React.CSSProperties) : undefined}>
                        <span className="companion__move-name">{move?.name ?? lm.id}</span>
                        <span className="companion__move-pp">
                          {lm.pp}/{lm.totalpp}
                        </span>
                        {inBattle && move && move.category !== "status" && type && (
                          <span className="companion__move-eff">
                            {foes.map((foe, j) => (
                              <Glyph key={j} mult={foe.member ? memberDefense(foe.member, type, byKey) : null} />
                            ))}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </MonCard>
          );
        })}
      </section>
    </div>
  );
}
