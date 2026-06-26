/* Learnset suggestion across a whole evolution line.

   A section-level mode switch sits at the top of the Learnset section: the
   `whole evolution line` toggle. Off (default) the section is the unchanged
   single-species {@link ProposedColumn}. On, one run asks the server to propose
   a learnset for every member of the line (base→tip, coherence threaded), and
   the result renders as a stack of per-stage panels — each its own
   current │ proposed diff with an independent Apply (the same read-merge-write
   the single-species path uses, one PUT per accepted stage).

   ponytail: line mode is review-and-apply, not fine-tune. Per-row inline editing,
   bulk level nudges, and alternative swaps stay on the single-species path; add
   them here only if the family-at-once flow proves to need them. */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../../api";
import { dexLabel } from "../../lib/format";
import type {
  DexEntry,
  LearnsetLineProposal as LineProposal,
  LearnsetLineStage,
  SpeciesOverride,
} from "../../types";
import { DexSprite } from "../DexSprite";
import { PokeballSpinner } from "../PokeballSpinner";
import { ProposedColumn } from "./ProposedColumn";
import { learnsetRenderer } from "./learnsetRenderer";
import { suggestLearnsetCall } from "./suggestCalls";
import { classifyProposed, mergeDraft, removedRows } from "./learnsetDraft";
import "./proposal.css";
import "./learnset-line.css";

const SECTION_ID = "learnset";

interface Props {
  entry: DexEntry;
  moveOptions: readonly string[];
  onSaved: () => void;
  onProposalActive: (sectionId: string, isActive: boolean) => void;
  backdropTargetId?: string | null;
  /** The read-only Learnset body shown under the single-species path while idle. */
  children: React.ReactNode;
}

/** The Learnset section: the line-mode toggle plus either the single-species
    proposer (off) or the whole-line proposer (on). */
export function LearnsetProposal({
  entry,
  moveOptions,
  onSaved,
  onProposalActive,
  backdropTargetId,
  children,
}: Props) {
  const [lineMode, setLineMode] = useState(false);
  // A species has a line if it has a pre-evolution or any forward edge.
  const hasLine =
    entry.evolution?.from != null || entry.evolves_into.length > 0;

  // Navigating to a species with no line drops line mode so the toggle never
  // strands the section in an empty whole-line view.
  useEffect(() => {
    if (!hasLine && lineMode) setLineMode(false);
  }, [hasLine, lineMode]);

  return (
    <div className="learnset-proposal">
      <div className="learnset-proposal__mode">
        <label
          className="learnset-proposal__line-toggle"
          htmlFor="learnset-line-toggle"
          title={hasLine ? undefined : "No evolution line."}
        >
          <input
            id="learnset-line-toggle"
            type="checkbox"
            checked={lineMode}
            disabled={!hasLine}
            onChange={(e) => setLineMode(e.target.checked)}
          />
          whole evolution line
        </label>
      </div>

      {lineMode ? (
        <LineProposalView
          entry={entry}
          onSaved={onSaved}
          onProposalActive={onProposalActive}
          backdropTargetId={backdropTargetId}
        />
      ) : (
        <ProposedColumn
          entry={entry}
          renderer={learnsetRenderer(moveOptions)}
          suggest={suggestLearnsetCall}
          onApplied={onSaved}
          onActiveChange={onProposalActive}
        >
          {children}
        </ProposedColumn>
      )}
    </div>
  );
}

type Phase = "input" | "loading" | "proposed" | "error";

interface LineViewProps {
  entry: DexEntry;
  onSaved: () => void;
  onProposalActive: (sectionId: string, isActive: boolean) => void;
  backdropTargetId?: string | null;
}

function LineProposalView({
  entry,
  onSaved,
  onProposalActive,
  backdropTargetId,
}: LineViewProps) {
  const [phase, setPhase] = useState<Phase>("input");
  const [direction, setDirection] = useState("");
  const [proposal, setProposal] = useState<LineProposal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // A single-stage Apply must NOT refetch the dex mid-run: the refetch remounts
  // this view and wipes the still-pending sibling stages. So stages write to
  // disk and flag dirty here; we flush ONE dex refresh when line mode closes
  // (this view unmounts). onSaved is read through a ref so the unmount cleanup
  // calls the latest one without re-subscribing.
  const dirtyRef = useRef(false);
  const onSavedRef = useRef(onSaved);
  onSavedRef.current = onSaved;

  // Line mode is an active proposal state for the whole time it's open, so the
  // ledger stays in its roomy layout (matches the single-species shell's signal).
  useEffect(() => {
    onProposalActive(SECTION_ID, true);
    return () => {
      onProposalActive(SECTION_ID, false);
      if (dirtyRef.current) onSavedRef.current();
    };
  }, [onProposalActive]);

  useEffect(() => {
    if (phase === "input") requestAnimationFrame(() => inputRef.current?.focus());
  }, [phase]);

  const run = useCallback(async () => {
    setPhase("loading");
    setError(null);
    try {
      const result = await api.suggestLearnsetLine(entry.chrooked_id, {
        direction: direction.trim() || undefined,
      });
      setProposal(result);
      setPhase("proposed");
    } catch (caught: unknown) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : caught instanceof Error
            ? caught.message
            : "Unexpected error",
      );
      setPhase("error");
    }
  }, [entry.chrooked_id, direction]);

  return (
    <section
      className="proposal proposal--section learnset-line"
      data-phase={phase}
      aria-label="Learnset across the evolution line"
    >
      <div className="proposal__head">
        <h3 className="ledger__heading proposal__heading">Learnset</h3>
        {phase === "loading" && (
          <PokeballSpinner
            id="learnset-line-spinner"
            size={20}
            label="Proposing across the line…"
          />
        )}
      </div>

      {(phase === "input" || phase === "proposed" || phase === "error") && (
        <form
          className="proposal__direction"
          onSubmit={(e) => {
            e.preventDefault();
            void run();
          }}
        >
          <label
            className="proposal__direction-label"
            htmlFor="learnset-line-direction"
          >
            Direction
          </label>
          <input
            ref={inputRef}
            id="learnset-line-direction"
            className="proposal__direction-input"
            type="text"
            value={direction}
            placeholder="how should the whole line learn? (optional)"
            onChange={(e) => setDirection(e.target.value)}
            autoComplete="off"
          />
          <button
            type="submit"
            id="learnset-line-submit"
            className="proposal__direction-submit"
          >
            {phase === "proposed" ? "Re-suggest" : "Propose line"}
          </button>
        </form>
      )}

      {phase === "loading" && proposal === null && (
        <p className="learnset-line__progress mono" aria-live="polite">
          One proposal per member, in evolution order. This runs the model once
          per stage, so it can take a moment.
        </p>
      )}

      {error !== null && (
        <p className="proposal__error" id="learnset-line-error" role="alert">
          <span className="proposal__error-tag mono" aria-hidden="true">
            no proposal
          </span>
          {error}
          <span className="sr-only"> — nothing was written.</span>
        </p>
      )}

      {phase === "proposed" && proposal !== null && (
        <LineStages
          proposal={proposal}
          backdropTargetId={backdropTargetId}
          onApplied={() => {
            dirtyRef.current = true;
          }}
        />
      )}
    </section>
  );
}

type StageStatus = "idle" | "applying" | "applied" | "error";

function LineStages({
  proposal,
  backdropTargetId,
  onApplied,
}: {
  proposal: LineProposal;
  backdropTargetId?: string | null;
  /** Mark the run dirty so the parent flushes one dex refresh when it closes. */
  onApplied: () => void;
}) {
  const [status, setStatus] = useState<Record<string, StageStatus>>({});
  const [applyError, setApplyError] = useState<Record<string, string>>({});

  const applyStage = useCallback(
    async (stage: LearnsetLineStage) => {
      if (stage.draft === null) return;
      setStatus((s) => ({ ...s, [stage.chrooked_id]: "applying" }));
      try {
        await writeStage(stage);
        setStatus((s) => ({ ...s, [stage.chrooked_id]: "applied" }));
        onApplied();
      } catch (caught: unknown) {
        setApplyError((e) => ({
          ...e,
          [stage.chrooked_id]:
            caught instanceof Error ? caught.message : "Unexpected error",
        }));
        setStatus((s) => ({ ...s, [stage.chrooked_id]: "error" }));
      }
    },
    [onApplied],
  );

  const pending = proposal.stages.filter(
    (s) => s.draft !== null && status[s.chrooked_id] !== "applied",
  );

  const applyAll = useCallback(async () => {
    // Sequential so the dex refetch storm stays one-at-a-time and a mid-batch
    // failure leaves the earlier writes committed (stages are independent).
    for (const stage of proposal.stages) {
      if (stage.draft === null) continue;
      if (status[stage.chrooked_id] === "applied") continue;
      await applyStage(stage);
    }
  }, [proposal.stages, status, applyStage]);

  return (
    <>
      <p className="learnset-line__chain mono" id="learnset-line-chain">
        {proposal.chain_label}
      </p>

      <ol className="learnset-line__stages" id="learnset-line-stages">
        {proposal.stages.map((stage) => (
          <StagePanel
            key={stage.chrooked_id}
            stage={stage}
            status={status[stage.chrooked_id] ?? "idle"}
            applyError={applyError[stage.chrooked_id] ?? null}
            backdropTargetId={backdropTargetId}
            onApply={() => void applyStage(stage)}
          />
        ))}
      </ol>

      <div className="proposal__actions learnset-line__actions">
        <button
          type="button"
          id="learnset-line-apply-all"
          className="proposal__apply"
          disabled={pending.length === 0}
          onClick={() => void applyAll()}
        >
          Apply all ({pending.length})
        </button>
      </div>
    </>
  );
}

function StagePanel({
  stage,
  status,
  applyError,
  backdropTargetId,
  onApply,
}: {
  stage: LearnsetLineStage;
  status: StageStatus;
  applyError: string | null;
  backdropTargetId?: string | null;
  onApply: () => void;
}) {
  const proposed = stage.draft?.learnset ?? [];
  const classified = classifyProposed(stage.current, proposed);
  const dropped = removedRows(stage.current, proposed);
  const reason = stage.rationale.learnset;
  const applied = status === "applied";

  return (
    <li
      className="learnset-line__stage"
      id={`learnset-line-stage-${stage.chrooked_id}`}
      data-anchor={stage.anchor || undefined}
      data-applied={applied || undefined}
    >
      <header className="learnset-line__stage-head">
        <DexSprite
          chrookedId={stage.chrooked_id}
          dex={stage.dex}
          name={stage.name}
          backdropTargetId={backdropTargetId}
          size={28}
        />
        <span className="learnset-line__stage-name">{stage.name}</span>
        <span className="learnset-line__stage-dex mono">
          {dexLabel(stage.dex)}
        </span>
        <span className="learnset-line__stage-badge mono">
          {stage.anchor ? "anchor" : "line"}
        </span>
        {applied && (
          <span className="learnset-line__stage-applied mono" aria-live="polite">
            ✓ applied
          </span>
        )}
      </header>

      {stage.error !== null ? (
        <p className="proposal__error" role="alert">
          <span className="proposal__error-tag mono" aria-hidden="true">
            no proposal
          </span>
          {stage.error}
        </p>
      ) : (
        <>
          <div className="proposal__columns">
            <div className="proposal__col">
              <p className="proposal__col-head">Current</p>
              <ol className="ledger__learnset proposal__learnset">
                {stage.current.length === 0 && (
                  <li className="lrow__empty">No level-up moves.</li>
                )}
                {[...stage.current]
                  .sort((a, b) => a.level - b.level || a.move.localeCompare(b.move))
                  .map((m, i) => {
                    const isDropped = dropped.some(
                      (d) => d.level === m.level && d.move === m.move,
                    );
                    return (
                      <li
                        key={`cur-${m.level}-${m.move}-${i}`}
                        className="ledger__move"
                        data-removed={isDropped}
                      >
                        <span className="ledger__move-lv mono">
                          {m.level === 0 ? "—" : `L${m.level}`}
                        </span>
                        <span className="ledger__move-name">{m.move}</span>
                        {isDropped && (
                          <span className="proposal-cell__marker mono">
                            → removed
                          </span>
                        )}
                      </li>
                    );
                  })}
              </ol>
            </div>

            <div className="proposal__col">
              <p className="proposal__col-head">Proposed</p>
              <ol className="ledger__learnset proposal__learnset">
                {classified.length === 0 && (
                  <li className="lrow__empty">No proposed moves.</li>
                )}
                {classified.map(({ row, status: rowStatus }) => {
                  const changed = rowStatus === "added";
                  return (
                    <li
                      key={`${row.level}-${row.move}`}
                      className={`ledger__move proposal__prow${changed ? " proposal-cell--changed" : ""}`}
                    >
                      <span className="ledger__move-lv mono">
                        {row.level === 0 ? "—" : `L${row.level}`}
                      </span>
                      <span className="ledger__move-name">{row.move}</span>
                      {changed && (
                        <span className="proposal-cell__marker mono">→ new</span>
                      )}
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>

          {reason && (
            <details className="proposal__why-design">
              <summary className="proposal__why-design-summary">
                Why this design
              </summary>
              <p className="proposal-cell__rationale proposal__why-design-body">
                {reason}
              </p>
            </details>
          )}

          {applyError !== null && (
            <p className="proposal__error" role="alert">
              <span className="proposal__error-tag mono" aria-hidden="true">
                rejected
              </span>
              {applyError}
            </p>
          )}

          {!applied && (
            <div className="proposal__actions">
              <button
                type="button"
                id={`learnset-line-apply-${stage.chrooked_id}`}
                className="proposal__apply"
                disabled={status === "applying" || stage.draft === null}
                onClick={onApply}
              >
                {status === "applying" ? "Applying…" : "Apply"}
              </button>
            </div>
          )}
        </>
      )}
    </li>
  );
}

/** The read-merge-write for one stage: fetch the member's raw Override (404 →
    seed the base identity so the merge touches only its learnset), merge the
    proposed learnset, then PUT. Mirrors ProposedColumn's single-species apply. */
async function writeStage(stage: LearnsetLineStage): Promise<void> {
  if (stage.draft === null) return;
  let raw: SpeciesOverride;
  try {
    raw = await api.speciesOverride(stage.chrooked_id);
  } catch {
    raw = {
      name: stage.name,
      chrooked_id: stage.chrooked_id,
      aka: stage.dex !== null ? { dex: stage.dex } : {},
      types: null,
      abilities: null,
      stats: null,
      learnset: null,
      evolution: null,
    };
  }
  // Silent: a per-stage write must NOT fire the global data-change, or the dex
  // refetch remounts this view and drops the still-pending sibling stages. The
  // parent flushes one refresh when line mode closes (its dirty-on-unmount path).
  await api.putSpecies(stage.chrooked_id, mergeDraft(raw, stage.draft), undefined, {
    silent: true,
  });
}
