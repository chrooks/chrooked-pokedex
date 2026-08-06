/* CREATE NEW move, driven through the EXISTING move-create Seam
   (POST /api/moves/suggest, mode: "create") — the same endpoint the chat skill
   uses (One Seam). Propose → preview (move stats + behavior STUB) → confirm →
   write in order: PUT move → PUT behavior (only if the draft carries a custom
   mechanic). engine_hints is NEVER filled (the human's grounding pass); the STUB
   note is surfaced honestly; the server refuses to clobber an id collision (422,
   shown verbatim). Mirrors AbilityCreatePanel, minus the distribution step (a move
   is distributed later, from the learnset). */

import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { api, ApiError } from "../../api";
import type { MoveWrite } from "../../types";
import { makeoverApi, type MoveCreateDraft, type MoveCreateResponse } from "../../lib/makeoverApi";
import { CategoryChip } from "../CategoryChip";
import type { StageActions } from "./StagePanel";

interface Props {
  redirectRef: RefObject<HTMLTextAreaElement>;
  registerActions: (actions: StageActions | null) => void;
  /** Record the created move's name so later suggest calls are steered to use it,
      and refresh the dex/move pool. The host closes the panel afterward. */
  onCreated: (name: string, kind: "move") => void;
  /** Return to the host stage (abilities / learnset) after a write or CANCEL. */
  onClose: () => void;
}

type Phase = "input" | "proposing" | "proposed" | "writing" | "error";

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Unexpected error";
}

/** Build the CRUD move payload from the drafted move, defaulting the fields the
    model may have omitted to the loader's defaults (effect "hit", target
    "selected", priority 0). aka/argument are the human's later grounding pass. */
function toMoveWrite(move: MoveCreateDraft["move"]): MoveWrite {
  return {
    name: move.name,
    chrooked_id: move.chrooked_id,
    aka: {},
    type: move.type,
    category: move.category,
    power: move.power ?? null,
    accuracy: move.accuracy ?? null,
    pp: move.pp ?? null,
    description: move.description ?? "",
    effect: move.effect ?? "hit",
    argument: null,
    additional_effects: move.additional_effects ?? [],
    flags: move.flags ?? [],
    priority: move.priority ?? 0,
    target: move.target ?? "selected",
  };
}

export function MoveCreatePanel({ redirectRef, registerActions, onCreated, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("input");
  const [direction, setDirection] = useState("");
  const [result, setResult] = useState<MoveCreateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function propose() {
    if (direction.trim() === "") return;
    setPhase("proposing");
    setError(null);
    try {
      const response = await makeoverApi.createMove(direction.trim());
      setResult(response);
      setPhase("proposed");
    } catch (caught: unknown) {
      setError(messageOf(caught));
      setPhase("error");
    }
  }

  const confirmRef = useRef<() => void>(() => {});
  confirmRef.current = () => {
    if (phase !== "proposed" || result === null) return;
    void (async () => {
      setPhase("writing");
      setError(null);
      try {
        await api.putMove(result.draft.move.chrooked_id, toMoveWrite(result.draft.move));
        // The behavior stub AS-IS — engine_hints stays {} (never filled here).
        if (result.draft.behavior) {
          await api.putBehavior(result.draft.behavior.chrooked_id, result.draft.behavior);
        }
        onCreated(result.draft.move.name, "move");
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
      focusRedirect: () => redirectRef.current?.focus(),
      canLock: phase === "proposed",
      phase,
    });
    return () => registerActions(null);
  }, [registerActions, redirectRef, phase]);

  const draft = result?.draft ?? null;
  const move = draft?.move ?? null;

  return (
    <div className="mk-create" id="mk-move-create" data-phase={phase}>
      <form
        className="mk-stage__redirect"
        onSubmit={(event) => {
          event.preventDefault();
          void propose();
        }}
      >
        <label className="mk-stage__redirect-label mono" htmlFor="mk-move-create-direction">
          new move
        </label>
        <textarea
          ref={redirectRef}
          id="mk-move-create-direction"
          className="mk-stage__redirect-input mono"
          rows={2}
          value={direction}
          placeholder="describe it (e.g. a Water priority move, 40 BP, that never misses)…"
          onChange={(event) => setDirection(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (phase !== "proposing" && phase !== "writing") void propose();
            }
          }}
          autoComplete="off"
        />
        <button
          type="submit"
          className="mk-btn mk-btn--ghost"
          disabled={phase === "proposing" || phase === "writing" || direction.trim() === ""}
        >
          {draft ? "TRY AGAIN" : "PROPOSE"}
        </button>
      </form>

      {phase === "proposing" && (
        <div className="mk-stage__skeleton" aria-busy="true" aria-live="polite">
          <span className="sr-only">Designing the move…</span>
          <span className="mk-skel-row" />
          <span className="mk-skel-card" />
          <span className="mk-skel-row" />
        </div>
      )}

      {error !== null && (
        <p className="mk-stage__error" role="alert">
          <span className="mk-stage__error-tag mono" aria-hidden="true">
            {phase === "error" && result ? "rejected" : "no proposal"}
          </span>
          {error}
        </p>
      )}

      {result?.warnings && result.warnings.length > 0 && (
        <ul className="mk-create__warnings" role="alert">
          {result.warnings.map((warning, i) => (
            <li key={i} className="mono">
              {warning}
            </li>
          ))}
        </ul>
      )}

      {draft && move && (
        <div className="mk-create__preview">
          <section className="mk-create__ability">
            <h4 className="mk-create__ability-name">
              {move.name} <span className="mono mk-create__id">{move.chrooked_id}</span>
            </h4>
            <dl className="mk-create__move-stats mono" id="mk-move-create-stats">
              <div>
                <dt>type</dt>
                <dd>{move.type}</dd>
              </div>
              <div>
                <dt>category</dt>
                <dd>
                  <CategoryChip category={move.category} variant="full" />
                </dd>
              </div>
              <div>
                <dt>power</dt>
                <dd>{move.power ?? "—"}</dd>
              </div>
              <div>
                <dt>accuracy</dt>
                <dd>{move.accuracy ?? "—"}</dd>
              </div>
              <div>
                <dt>pp</dt>
                <dd>{move.pp ?? "—"}</dd>
              </div>
              <div>
                <dt>priority</dt>
                <dd>{move.priority ?? 0}</dd>
              </div>
            </dl>
            {move.description && <p className="mk-create__ability-desc">{move.description}</p>}
          </section>

          {draft.behavior && (
            <section className="mk-create__behavior">
              <h5 className="mk-create__sub mono">behavior stub</h5>
              <ul className="mk-create__effects">
                {draft.behavior.effects.map((effect, i) => (
                  <li key={i}>
                    <span className="mono mk-create__trigger">{effect.trigger}</span> {effect.summary}
                  </li>
                ))}
              </ul>
              <p className="mk-create__stub mono">
                engine_hints: {"{}"} — STUB, needs a human grounding pass (never auto-filled).
              </p>
            </section>
          )}

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
              id="mk-move-create-confirm"
              className="mk-btn mk-btn--lock"
              disabled={phase === "writing"}
              onClick={() => confirmRef.current()}
            >
              {phase === "writing" ? "WRITING…" : "CREATE MOVE"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
