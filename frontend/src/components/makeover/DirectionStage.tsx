/* The DIRECTION stage — the makeover opening move. Fetches 2-3 lore-grounded
   typing+role options from the species-suggest Seam (mode: lore-options) and
   presents them as pickable cards, plus a free-direction input. Picking a card or
   submitting the free input chooses the direction and advances to TYPING. Nothing
   is written here — direction only steers the later stages (ac2). */

import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../api";
import type { AbilitySlots, DexEntry } from "../../types";
import { makeoverApi, type LoreOption } from "../../lib/makeoverApi";
import type { StageActions } from "./StagePanel";

interface Props {
  entry: DexEntry;
  redirectRef: React.RefObject<HTMLInputElement>;
  registerActions: (actions: StageActions | null) => void;
  /** Chosen direction → advance to typing, carrying the steer forward. */
  onChosen: (direction: string) => void;
  /** Current typing when TYPING is KEPT (à la carte) — options keep it verbatim
      and differ only by role. Undefined when typing is in play. */
  keptTypes?: string[];
  /** Current abilities when ABILITIES is KEPT — options must not hinge on new ones. */
  keptAbilities?: AbilitySlots;
}

type Phase = "idle" | "loading" | "ready" | "error";

/** The direction string a picked option carries into the typing stage. */
function optionDirection(option: LoreOption): string {
  return `${option.role} — typing ${option.types.join("/")}`;
}

export function DirectionStage({
  entry,
  redirectRef,
  registerActions,
  onChosen,
  keptTypes,
  keptAbilities,
}: Props) {
  // ac13: lore options load ON DEMAND (SUGGEST DIRECTIONS), never on mount — the
  // free-direction path stays entirely call-free. `idle` is the opening state.
  const [phase, setPhase] = useState<Phase>("idle");
  const [options, setOptions] = useState<LoreOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [free, setFree] = useState("");
  const typingKept = keptTypes != null;

  // Read the kept-facet constraints through a ref so the load callback stays stable.
  const keptRef = useRef({ keptTypes, keptAbilities });
  keptRef.current = { keptTypes, keptAbilities };

  async function loadOptions() {
    setPhase("loading");
    setError(null);
    try {
      const result = await makeoverApi.loreOptions(entry.chrooked_id, {
        keptTypes: keptRef.current.keptTypes,
        keptAbilities: keptRef.current.keptAbilities,
      });
      setOptions(result.draft.options);
      setPhase("ready");
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
  }

  // The workbench's Enter = LOCK IN maps here to "use the free direction" when the
  // author has typed one; `t` focuses the free-direction input.
  const freeRef = useRef(free);
  freeRef.current = free;
  useEffect(() => {
    registerActions({
      lockIn: () => {
        const text = freeRef.current.trim();
        if (text) onChosen(text);
      },
      focusRedirect: () => redirectRef.current?.focus(),
      canLock: free.trim() !== "",
      phase,
    });
    return () => registerActions(null);
  }, [registerActions, redirectRef, onChosen, free, phase]);

  return (
    <div className="mk-stage" data-phase={phase} id="mk-stage-direction">
      <p className="mk-direction__lead">
        Pick a lore-grounded direction for <strong>{entry.name}</strong>, or write your own.
        {typingKept && (
          <>
            {" "}
            <span className="mk-direction__kept-note mono">
              typing kept · {keptTypes?.join("/")}
            </span>
          </>
        )}
      </p>

      {(phase === "idle" || phase === "error") && (
        <button
          type="button"
          className="mk-btn mk-btn--ghost"
          id="mk-suggest-directions"
          onClick={() => void loadOptions()}
        >
          {phase === "error" ? "TRY AGAIN" : "SUGGEST DIRECTIONS"}
        </button>
      )}

      {phase === "loading" && (
        <div className="mk-stage__skeleton" aria-busy="true" aria-live="polite">
          <span className="sr-only">Researching the line…</span>
          <span className="mk-skel-card" />
          <span className="mk-skel-card" />
          <span className="mk-skel-card" />
        </div>
      )}

      {phase === "error" && error !== null && (
        <p className="mk-stage__error" role="alert">
          <span className="mk-stage__error-tag mono" aria-hidden="true">
            no proposal
          </span>
          {error}
          <span className="sr-only"> — nothing was written. Write your own direction below.</span>
        </p>
      )}

      {phase === "ready" && (
        <ul className="mk-direction__options" id="mk-direction-options">
          {options.map((option, index) => (
            <li key={index}>
              <button
                type="button"
                className="mk-direction__option"
                id={`mk-direction-option-${index}`}
                onClick={() => onChosen(optionDirection(option))}
              >
                <span className="mk-direction__types mono" data-kept={typingKept || undefined}>
                  {option.types.join(" / ")}
                  {typingKept && <span className="mk-direction__kept-tag">kept</span>}
                </span>
                <span className="mk-direction__role">{option.role}</span>
                <span className="mk-direction__why">{option.rationale}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <form
        className="mk-direction__free"
        onSubmit={(event) => {
          event.preventDefault();
          const text = free.trim();
          if (text) onChosen(text);
        }}
      >
        <label className="mk-stage__redirect-label mono" htmlFor="mk-direction-free">
          your direction
        </label>
        <input
          ref={redirectRef}
          id="mk-direction-free"
          className="mk-stage__redirect-input mono"
          type="text"
          value={free}
          placeholder="e.g. lean into the trapper role"
          onChange={(event) => setFree(event.target.value)}
          autoComplete="off"
        />
        <button type="submit" className="mk-btn mk-btn--lock" disabled={free.trim() === ""}>
          USE THIS
        </button>
      </form>
    </div>
  );
}
