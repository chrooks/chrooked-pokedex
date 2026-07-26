/* DISTRIBUTE a MOVE onto species learnsets — the learnset twin of DistributePanel.
   Pick a known move (or prefilled + locked via `initialMove`), add species + a
   level per row, DISTRIBUTE merges each (level, move) row into its species
   learnset (other rows preserved). Reuses the pure moveDistribution ops and the
   shared writeMoveDistribution. */

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../../api";
import type { DexEntry } from "../../types";
import { evoLine } from "../../lib/evoLine";
import { addRow, deriveCurrentLevel, type MoveDistRow } from "./moveDistribution";
import {
  allLineIds,
  groupByLine,
  includedMemberCount,
  lineIdOf,
  toggleIncluded,
  topLineIds,
} from "./distributionLines";
import { LineDistribution } from "./LineDistribution";
import { writeMoveDistribution } from "./moveDistributionWrite";
import type { StageActions } from "./StagePanel";

/** The opt-in AI distribution result (✦ Suggest) for a move: proposed
    {species, level} rows plus an optional rationale and dropped-species warnings. */
export interface MoveSuggestResult {
  rows: MoveDistRow[];
  rationale?: string;
  warnings?: string[];
}

const DEFAULT_LEVEL = 1;
const MIN_LEVEL = 0;
const MAX_LEVEL = 100;

/** The pre-request size budget (evolution FAMILIES): default + range. Set BEFORE
    ✦ Suggest, it bounds the ASK so a broad move returns ~N best-fit lines, not a
    huge set. The server clamps to this same range. The post-request breadth slider
    then trims DOWN within the returned set — to get MORE, raise this and ✦ Suggest
    again (the only LLM call stays the explicit button). */
const DEFAULT_SIZE_BUDGET = 12;
const MIN_SIZE_BUDGET = 1;
const MAX_SIZE_BUDGET = 40;

interface Props {
  byId: ReadonlyMap<string, DexEntry>;
  moveOptions: readonly string[];
  registerActions: (actions: StageActions | null) => void;
  /** Refresh the dex after the distribution lands (a side write). */
  onSaved: () => void;
  /** Return to the host after a write or CANCEL. */
  onClose: () => void;
  /** When set, the move is fixed to this one — the picker is locked to a label
      (used by the create→distribute step). Default (undefined) = pick-your-own. */
  initialMove?: string;
  /** Opt-in AI distribution (✦ Suggest). Given the resolved move name and the
      author's freeform direction (may be empty → the caller falls back to a
      type/split rule), returns proposed {species, level} rows. Absent → NO ✦
      Suggest button. Fires ONLY on the explicit click. `limit` is the pre-request
      size budget (evolution families) the author set before the click. */
  onSuggest?: (
    moveName: string,
    direction: string,
    limit: number,
  ) => Promise<MoveSuggestResult>;
}

type Phase = "input" | "writing" | "error";

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Unexpected error";
}

function clampLevel(value: number): number {
  if (Number.isNaN(value)) return MIN_LEVEL;
  return Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, Math.trunc(value)));
}

export function MoveDistributePanel({
  byId,
  moveOptions,
  registerActions,
  onSaved,
  onClose,
  initialMove,
  onSuggest,
}: Props) {
  const locked = initialMove !== undefined && initialMove.trim() !== "";
  const [phase, setPhase] = useState<Phase>("input");
  const [move, setMove] = useState(initialMove ?? "");
  // The full suggested/added set is the source of truth; the grouped view, the
  // include set, and the per-line level map all derive from it.
  const [dist, setDist] = useState<MoveDistRow[]>([]);
  // Included evo lines (by lineId). `included.size` is the breadth slider's K, so
  // a slider move (top-K) and a manual toggle stay in sync by construction.
  const [included, setIncluded] = useState<Set<string>>(() => new Set());
  // Author overrides of a line's level; the default comes from the proposal rows.
  const [levelOverride, setLevelOverride] = useState<Map<string, number>>(() => new Map());
  const [addSpecies, setAddSpecies] = useState("");
  const [addLevel, setAddLevel] = useState(DEFAULT_LEVEL);
  const [error, setError] = useState<string | null>(null);
  // The author's freeform steer for ✦ Suggest — empty falls back to a type/split
  // rule (the caller decides). Long-form so a real sentence of intent fits.
  const [direction, setDirection] = useState("");
  // The pre-request size budget (evolution families) — how many best-fit lines to
  // ASK for. Bounds the request; the post-request breadth slider trims within it.
  const [sizeBudget, setSizeBudget] = useState(DEFAULT_SIZE_BUDGET);
  // ✦ Suggest (opt-in AI) — never fires without the button click below.
  const [suggesting, setSuggesting] = useState(false);
  const [suggestNote, setSuggestNote] = useState<string | null>(null);
  const [suggestWarnings, setSuggestWarnings] = useState<string[]>([]);
  const moveRef = useRef<HTMLInputElement>(null);

  // When locked the move is trusted (the author just created it, so it may not be
  // in moveOptions until the parent reload lands); otherwise it must be a known move.
  const knownMove = locked || (move.trim() !== "" && moveOptions.includes(move.trim()));

  const idByName = useMemo(() => {
    const map = new Map<string, string>();
    for (const member of byId.values()) map.set(member.name.toLowerCase(), member.chrooked_id);
    return map;
  }, [byId]);
  const resolvedAddId =
    idByName.get(addSpecies.trim().toLowerCase()) ??
    (byId.has(addSpecies.trim()) ? addSpecies.trim() : null);

  // Fold the source-of-truth rows into evo-line groups (ordered by first
  // appearance). Pure trim + grouping — no LLM call.
  const groups = useMemo(() => groupByLine(dist, byId), [dist, byId]);
  // Default level per line: the first present member's proposed level. Author
  // edits land in levelOverride and win.
  const defaultLineLevel = useMemo(() => {
    const map = new Map<string, number>();
    for (const row of dist) {
      const id = lineIdOf(row.species, byId);
      if (!map.has(id)) map.set(id, row.level);
    }
    return map;
  }, [dist, byId]);
  const levelOf = (lineId: string): number =>
    levelOverride.get(lineId) ?? defaultLineLevel.get(lineId) ?? DEFAULT_LEVEL;

  const includedLineCount = groups.filter((g) => included.has(g.lineId)).length;
  const includedMons = includedMemberCount(groups, included);

  function commitAdd() {
    if (resolvedAddId === null) return;
    const lineId = lineIdOf(resolvedAddId, byId);
    setDist((rows) => addRow(rows, { species: resolvedAddId, level: clampLevel(addLevel) }));
    setIncluded((prev) => new Set(prev).add(lineId)); // a manual add is included
    setAddSpecies("");
  }

  // ＋ line: add every member of the resolved species' evolution family at the
  // add-row's level (deduped by addRow). Same level for the whole line.
  function commitAddLine() {
    if (resolvedAddId === null) return;
    const entry = byId.get(resolvedAddId);
    if (entry === undefined) return;
    const lineId = lineIdOf(resolvedAddId, byId);
    const level = clampLevel(addLevel);
    const family = evoLine(entry, byId);
    setDist((rows) =>
      family.reduce((acc, member) => addRow(acc, { species: member.chrooked_id, level }), rows),
    );
    setIncluded((prev) => new Set(prev).add(lineId));
    setAddSpecies("");
  }

  // Remove a whole line: drop its members from the source rows and un-include it.
  function removeLine(lineId: string) {
    const members = new Set(groups.find((g) => g.lineId === lineId)?.members ?? []);
    setDist((rows) => rows.filter((r) => !members.has(r.species)));
    setIncluded((prev) => {
      const next = new Set(prev);
      next.delete(lineId);
      return next;
    });
  }

  // Whether/at what level the resolved add-row species already learns this move —
  // a live "currently: L{n}" / "not learned" hint before the ADD click.
  const addCurrentLevel =
    resolvedAddId !== null && knownMove
      ? deriveCurrentLevel(byId, resolvedAddId, move.trim())
      : null;

  // ✦ Suggest (opt-in): fires ONLY here, on the explicit button click. Populates
  // the editable rows from the AI proposal; the author still edits before writing.
  async function runSuggest() {
    if (onSuggest === undefined || !knownMove || suggesting) return;
    setSuggesting(true);
    setError(null);
    setSuggestNote(null);
    setSuggestWarnings([]);
    try {
      const result = await onSuggest(move.trim(), direction.trim(), sizeBudget);
      const nextRows = result.rows.map((row) => ({
        species: row.species,
        level: clampLevel(row.level),
      }));
      setDist(nextRows);
      setLevelOverride(new Map());
      // The request was BOUNDED to sizeBudget families, so the returned set is
      // already scannable — include it all. The post-request breadth slider trims
      // DOWN within it; to get MORE, raise the size budget and ✦ Suggest again.
      const nextGroups = groupByLine(nextRows, byId);
      setIncluded(new Set(allLineIds(nextGroups)));
      const budgetNote =
        `Got ${nextGroups.length} of up to ${sizeBudget} lines. Trim below to ` +
        "include fewer; raise the size and ✦ Suggest again for more.";
      setSuggestNote(
        nextGroups.length === 0
          ? "The suggestion named no in-dex species — add some below."
          : result.rationale
            ? `${result.rationale} — ${budgetNote}`
            : budgetNote,
      );
      setSuggestWarnings(result.warnings ?? []);
    } catch (caught: unknown) {
      setError(messageOf(caught));
    } finally {
      setSuggesting(false);
    }
  }

  const canConfirm = knownMove && includedMons > 0;

  const confirmRef = useRef<() => void>(() => {});
  confirmRef.current = () => {
    if (!canConfirm) return;
    // Materialize only the INCLUDED lines → one species row per present member at
    // that line's level. The excluded (dimmed) lines are never written.
    const outRows: MoveDistRow[] = groups
      .filter((group) => included.has(group.lineId))
      .flatMap((group) =>
        group.members.map((species) => ({ species, level: levelOf(group.lineId) })),
      );
    void (async () => {
      setPhase("writing");
      setError(null);
      try {
        await writeMoveDistribution(move.trim(), outRows, byId);
        onSaved();
        onClose();
      } catch (caught: unknown) {
        setError(`${messageOf(caught)} — partial writes may have landed (git is the undo).`);
        setPhase("error");
      }
    })();
  };

  useEffect(() => {
    registerActions({
      lockIn: () => confirmRef.current(),
      focusRedirect: () => moveRef.current?.focus(),
      canLock: canConfirm,
      phase,
    });
    return () => registerActions(null);
  }, [registerActions, canConfirm, phase]);

  return (
    <div className="mk-create" id="mk-move-distribute" data-phase={phase}>
      <div className="mk-stage__redirect">
        <label className="mk-stage__redirect-label mono" htmlFor="mk-move-distribute-move">
          move
        </label>
        {locked ? (
          <span className="mk-move-distribute__locked mono" id="mk-move-distribute-move">
            {move}
          </span>
        ) : (
          <>
            <input
              ref={moveRef}
              id="mk-move-distribute-move"
              className="mk-stage__redirect-input mono"
              type="text"
              list="mk-move-distribute-move-list"
              value={move}
              placeholder="pick an existing move to distribute…"
              onChange={(event) => setMove(event.target.value)}
              autoComplete="off"
            />
            <datalist id="mk-move-distribute-move-list">
              {moveOptions.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </>
        )}
      </div>

      {error !== null && (
        <p className="mk-stage__error" role="alert">
          <span className="mk-stage__error-tag mono" aria-hidden="true">
            rejected
          </span>
          {error}
        </p>
      )}

      <section className="mk-create__dist" id="mk-move-distribute-dist">
        {onSuggest !== undefined && (
          <div className="mk-dist-direction">
            <label className="mk-stage__redirect-label mono" htmlFor="mk-move-distribute-direction">
              direction <span className="mk-dist-direction__opt">— optional, steers ✦ Suggest</span>
            </label>
            <textarea
              id="mk-move-distribute-direction"
              className="mk-stage__redirect-input mono"
              rows={2}
              value={direction}
              placeholder="e.g. fast physical attackers and bug-catchers…"
              onChange={(event) => setDirection(event.target.value)}
            />
            <div className="mk-dist-budget" id="mk-move-distribute-budget">
              <label className="mk-linedist__slider-label mono" htmlFor="mk-move-distribute-size">
                size: <span className="mk-linedist__k">{sizeBudget}</span> evo lines to request
              </label>
              <input
                type="range"
                id="mk-move-distribute-size"
                className="mk-linedist__slider"
                min={MIN_SIZE_BUDGET}
                max={MAX_SIZE_BUDGET}
                step={1}
                value={sizeBudget}
                onChange={(event) => setSizeBudget(Number(event.target.value))}
                aria-label={`Distribution size budget: ${sizeBudget} evolution lines to request`}
              />
            </div>
          </div>
        )}
        <div className="mk-dist-head">
          <h5 className="mk-create__sub mono">
            distribution ({includedMons} {includedMons === 1 ? "mon" : "mons"} ·{" "}
            {includedLineCount} {includedLineCount === 1 ? "line" : "lines"})
          </h5>
          {onSuggest !== undefined && (
            <button
              type="button"
              id="mk-move-distribute-suggest"
              className="mk-suggest mono"
              disabled={!knownMove || suggesting}
              title={
                knownMove
                  ? "Suggest fitting species with AI (fills the rows — you still edit)"
                  : "Pick a move first"
              }
              onClick={() => void runSuggest()}
            >
              <span aria-hidden="true">✦ </span>
              {suggesting ? "suggesting…" : "Suggest"}
            </button>
          )}
        </div>
        {suggestNote !== null && (
          <p className="mk-dist-note mono" id="mk-move-distribute-suggest-note" aria-live="polite">
            {suggestNote}
          </p>
        )}
        {suggestWarnings.length > 0 && (
          <ul className="mk-create__warnings" id="mk-move-distribute-suggest-warnings" role="alert">
            {suggestWarnings.map((warning, i) => (
              <li key={i} className="mono">
                {warning}
              </li>
            ))}
          </ul>
        )}
        {groups.length > 0 ? (
          <LineDistribution
            groups={groups}
            byId={byId}
            included={included}
            idPrefix="mk-move-distribute"
            onSlider={(k) => setIncluded(new Set(topLineIds(groups, k)))}
            onToggleLine={(lineId) => setIncluded((prev) => toggleIncluded(prev, lineId))}
            onRemoveLine={removeLine}
            onAll={() => setIncluded(new Set(allLineIds(groups)))}
            onNone={() => setIncluded(new Set())}
            renderValue={(group) => (
              <input
                className="mk-num mono mk-linedist__value"
                type="number"
                inputMode="numeric"
                min={MIN_LEVEL}
                max={MAX_LEVEL}
                aria-label={`${group.members.map((m) => byId.get(m)?.name ?? m).join(", ")} level`}
                value={levelOf(group.lineId)}
                onChange={(event) =>
                  setLevelOverride((prev) =>
                    new Map(prev).set(group.lineId, clampLevel(Number(event.target.value))),
                  )
                }
              />
            )}
            renderDetail={(group) => (
              <>
                currently —{" "}
                {group.members.map((m, i) => {
                  const name = byId.get(m)?.name ?? m;
                  const cur = deriveCurrentLevel(byId, m, move.trim());
                  return (
                    <span key={m}>
                      {i > 0 ? " · " : ""}
                      {name}:{" "}
                      {cur !== null ? (
                        <span className="mk-linedist__rep-has">L{cur}</span>
                      ) : (
                        <span className="mk-linedist__rep-new">not learned</span>
                      )}
                    </span>
                  );
                })}
              </>
            )}
          />
        ) : (
          <p className="mk-empty mono">no species yet — add one below.</p>
        )}

        <div className="mk-dist-add" id="mk-move-distribute-add">
          <input
            className="mk-stage__redirect-input mono"
            id="mk-move-distribute-add-species"
            type="text"
            list="mk-move-distribute-species-list"
            aria-label="Add a species to the distribution"
            placeholder="add a species…"
            value={addSpecies}
            onChange={(event) => setAddSpecies(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                commitAdd();
              }
            }}
            autoComplete="off"
          />
          <datalist id="mk-move-distribute-species-list">
            {[...byId.values()].map((member) => (
              <option key={member.chrooked_id} value={member.name} />
            ))}
          </datalist>
          <input
            className="mk-num mono"
            id="mk-move-distribute-add-level"
            type="number"
            inputMode="numeric"
            min={MIN_LEVEL}
            max={MAX_LEVEL}
            aria-label="Level for the added species"
            value={addLevel}
            onChange={(event) => setAddLevel(clampLevel(Number(event.target.value)))}
          />
          <button
            type="button"
            className="mk-btn mk-btn--ghost"
            id="mk-move-distribute-add-btn"
            disabled={resolvedAddId === null}
            title={resolvedAddId === null ? "Type a known species name" : "Add to distribution"}
            onClick={commitAdd}
          >
            ADD
          </button>
          <button
            type="button"
            className="mk-btn mk-btn--ghost"
            id="mk-move-distribute-add-line"
            disabled={resolvedAddId === null}
            title={
              resolvedAddId === null
                ? "Type a known species name"
                : "Add this species' whole evolution line at this level"
            }
            onClick={commitAddLine}
          >
            ＋ line
          </button>
        </div>
        {resolvedAddId !== null && (
          <p className="mk-dist-add__hint mono" id="mk-move-distribute-add-current" aria-live="polite">
            {addCurrentLevel !== null ? `currently: L${addCurrentLevel}` : "not learned"}
          </p>
        )}
      </section>

      <div className="mk-stage__actions">
        <button
          type="button"
          className="mk-btn mk-btn--ghost mono"
          onClick={onClose}
          disabled={phase === "writing"}
        >
          CANCEL
        </button>
        <button
          type="button"
          id="mk-move-distribute-confirm"
          className="mk-btn mk-btn--lock"
          disabled={!canConfirm || phase === "writing"}
          title={canConfirm ? "Distribute this move" : "Pick a move and at least one species"}
          onClick={() => confirmRef.current()}
        >
          {phase === "writing" ? "WRITING…" : "DISTRIBUTE"}
        </button>
      </div>
    </div>
  );
}
