/* The shared chrome for a design stage: the redirect (re-roll) box, the skeleton
   loader (no spinner), the verbatim error, the swappable alternatives, and the
   LOCK IN / TRY AGAIN buttons. Section-agnostic — the section-specific cell grid
   is passed as children (the typing chips, the stat rows, the ability slots, the
   learnset diff). Device voice throughout: LOCK IN, TRY AGAIN — no celebration. */

import { useEffect, useRef } from "react";
import type { ReactNode, RefObject } from "react";
import type { ProposalAlternative } from "../../types";
import { PokeballSpinner } from "../PokeballSpinner";
import type { UseMakeoverStage } from "./useMakeoverStage";

/** The imperative handle the workbench keyboard drives (Enter = LOCK IN, t =
    focus redirect). Registered by the active stage; null between stages. */
export interface StageActions {
  lockIn: () => void;
  focusRedirect: () => void;
  canLock: boolean;
  phase: string;
}

interface Props<Draft> {
  /** Device-voice stage label, e.g. "TYPING". */
  stageLabel: string;
  hook: UseMakeoverStage<Draft>;
  /** Lock gating from the stage machine — a locked-out LOCK IN is disabled. */
  canLock: boolean;
  placeholder: string;
  redirectRef: RefObject<HTMLTextAreaElement>;
  registerActions: (actions: StageActions | null) => void;
  /** An optional control rendered beside the redirect button (e.g. the learnset
      stage's "＋ new move" affordance). */
  extraControl?: ReactNode;
  /** Swap an alternative into the current draft (section-specific). */
  applyAlternative?: (alt: ProposalAlternative, draft: Draft | null) => Draft;
  /** A compact label for an alternative value (section-specific). */
  altLabel?: (value: unknown) => string;
  /** The stage's current-state view, shown in the READY (pre-proposal) phase so
      the author sees what's there before spending a call (ac13). */
  current?: ReactNode;
  /** The current │ proposed cell grid. */
  children: ReactNode;
}

export function StagePanel<Draft>({
  stageLabel,
  hook,
  canLock,
  placeholder,
  redirectRef,
  registerActions,
  applyAlternative,
  altLabel,
  current,
  children,
  extraControl,
}: Props<Draft>) {
  const {
    phase,
    direction,
    draft,
    rationale,
    alternatives,
    error,
    errorKind,
    setDirection,
    propose,
    editDraft,
    lockIn,
  } = hook;

  // ac13: no auto-propose. The stage opens in a call-free READY view; PROPOSE (the
  // form submit / button) spends the first call only when the author is ready.

  // Register the imperative actions for the workbench keyboard path. Re-registers
  // whenever lock-ability changes; clears on unmount so a stale handle never fires.
  const lockRef = useRef(lockIn);
  lockRef.current = lockIn;
  const canLockNow = phase === "proposed" && draft !== null && canLock;
  useEffect(() => {
    registerActions({
      lockIn: () => void lockRef.current(),
      focusRedirect: () => redirectRef.current?.focus(),
      canLock: canLockNow,
      phase,
    });
    return () => registerActions(null);
  }, [registerActions, redirectRef, canLockNow, phase]);

  const isProposing = phase === "proposing";
  const isLocking = phase === "locking";
  const proposed = phase === "proposed" && draft !== null;
  const sectionReason = rationale[stageLabel.toLowerCase()] ?? Object.values(rationale)[0];

  return (
    <div className="mk-stage" data-phase={phase} id={`mk-stage-${stageLabel.toLowerCase()}`}>
      <form
        className="mk-stage__redirect"
        onSubmit={(event) => {
          event.preventDefault();
          void propose();
        }}
      >
        <label className="mk-stage__redirect-label mono" htmlFor="mk-redirect">
          {phase === "propose" ? "direction" : "redirect"}
        </label>
        <textarea
          ref={redirectRef}
          id="mk-redirect"
          className="mk-stage__redirect-input mono"
          rows={2}
          value={direction}
          placeholder={placeholder}
          onChange={(event) => setDirection(event.target.value)}
          onKeyDown={(event) => {
            // Enter submits (re-roll); Shift+Enter inserts a newline.
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (!isProposing && !isLocking) void propose();
            }
          }}
          autoComplete="off"
        />
        <button
          type="submit"
          id="mk-reroll"
          className="mk-btn mk-btn--ghost"
          disabled={isProposing || isLocking}
        >
          {proposed ? "TRY AGAIN" : "PROPOSE"}
        </button>
        {extraControl}
      </form>

      {phase === "propose" && (
        <div className="mk-stage__ready" id={`mk-ready-${stageLabel.toLowerCase()}`}>
          {current}
          <p className="mk-stage__hint mono">no call yet — PROPOSE when ready (Enter)</p>
        </div>
      )}

      {isProposing && (
        <div className="mk-stage__skeleton" aria-live="polite" aria-busy="true">
          <span className="sr-only">Proposing…</span>
          <span className="mk-skel-row" />
          <span className="mk-skel-row" />
          <span className="mk-skel-row" />
        </div>
      )}

      {error !== null && (
        <p className="mk-stage__error" id="mk-stage-error" role="alert">
          <span className="mk-stage__error-tag mono" aria-hidden="true">
            {errorKind === "lock" ? "rejected" : "no proposal"}
          </span>
          {error}
          <span className="sr-only"> — nothing was written.</span>
        </p>
      )}

      {proposed && <div className="mk-stage__cells">{children}</div>}

      {proposed && sectionReason && (
        <details className="mk-stage__why">
          <summary className="mk-stage__why-summary mono">why this design</summary>
          <p className="mk-stage__why-body">{sectionReason}</p>
        </details>
      )}

      {proposed && alternatives.length > 0 && applyAlternative && (
        <details className="mk-stage__alts">
          <summary className="mk-stage__alts-summary mono">
            alternatives ({alternatives.length})
          </summary>
          <ul className="mk-stage__alts-list">
            {alternatives.map((alt, index) => (
              <li key={index}>
                <button
                  type="button"
                  className="mk-stage__alt"
                  onClick={() => editDraft(applyAlternative(alt, draft))}
                >
                  <span className="mono mk-stage__alt-value">
                    {altLabel ? altLabel(alt.value) : String(alt.value)}
                  </span>
                  {alt.rationale && (
                    <span className="mk-stage__alt-why">{alt.rationale}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}

      {proposed && (
        <div className="mk-stage__actions">
          <button
            type="button"
            id="mk-lock-in"
            className="mk-btn mk-btn--lock"
            disabled={!canLockNow || isLocking}
            onClick={() => void lockIn()}
            title={canLock ? "Write this stage (Enter)" : "Lock the earlier stages first"}
          >
            {isLocking ? "LOCKING…" : "LOCK IN"}
          </button>
          {isLocking && (
            <PokeballSpinner id="mk-lock-spinner" size={20} label="Writing the Ruleset…" />
          )}
        </div>
      )}
    </div>
  );
}
