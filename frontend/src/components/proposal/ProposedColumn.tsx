/* The generic proposed-column shell. Section-agnostic: it owns the whole flow
   (the `✦ suggest` affordance, the direction input, the Poké Ball loader, the
   rationale block, the swappable alternatives, the Apply button, and every
   state) and delegates ONLY the current │ proposed cell grid + the draft→Override
   mapping to an injected {@link SectionRenderer}. The same shell drives both the
   abilities and the learnset sections (ac7); #32/#8 reuse it later unchanged.

   Apply is read-merge-write (mirrors SpeciesEditor): fetch the raw Override
   (404 → a base `{name, chrooked_id}`), let the renderer merge ONLY its one
   section's patch, then PUT — never clobbering untouched Override fields. */

import { useCallback, useEffect, useMemo, useRef } from "react";
import type { ReactNode } from "react";
import { api } from "../../api";
import type { DexEntry, SpeciesOverride } from "../../types";
import { PokeballSpinner } from "../PokeballSpinner";
import type { SectionRenderer } from "./renderer";
import { sectionBody } from "./suggestMachine";
import { useSuggest } from "./useSuggest";
import "./proposal.css";

interface Props<Draft> {
  entry: DexEntry;
  renderer: SectionRenderer<Draft>;
  /** The /suggest call for this section (injected, so the shell stays generic). */
  suggest: (
    id: string,
    direction: string,
  ) => Promise<{
    draft: Draft;
    rationale: Record<string, string>;
    alternatives: { value: unknown; rationale: string }[];
  }>;
  /** Refresh the ledger after a clean Apply so the merged view reflects it. */
  onApplied: () => void;
  /** Report this section's active/idle state so the ledger can auto-expand when
      any section has a proposal in flight (ac8 / P1). Active = any non-idle phase. */
  onActiveChange?: (sectionId: string, isActive: boolean) => void;
  /** The section's read-only body. It shows under the single section heading while
      idle and BECOMES the "Current" column once a proposal is active (the renderer
      then draws current │ proposed itself, so this is hidden to avoid duplication). */
  children: ReactNode;
}

/** Build the read-merge-write Apply for this section. Generic over the draft. */
function useApply<Draft>(
  entry: DexEntry,
  renderer: SectionRenderer<Draft>,
): (draft: Draft) => Promise<unknown> {
  return useCallback(
    async (draft: Draft) => {
      let raw: SpeciesOverride;
      try {
        raw = await api.speciesOverride(entry.chrooked_id);
      } catch {
        // 404 (or any read miss) = no Override yet; seed the base identity so the
        // merge writes only this one section and nothing else.
        raw = {
          name: entry.name,
          chrooked_id: entry.chrooked_id,
          aka: entry.dex !== null ? { dex: entry.dex } : {},
          types: null,
          abilities: null,
          stats: null,
          learnset: null,
          evolution: null,
        };
      }
      const merged = renderer.mergeDraft(raw, draft);
      return api.putSpecies(entry.chrooked_id, merged);
    },
    [entry, renderer],
  );
}

export function ProposedColumn<Draft>({
  entry,
  renderer,
  suggest,
  onApplied,
  onActiveChange,
  children,
}: Props<Draft>) {
  const inputRef = useRef<HTMLInputElement>(null);

  const suggestCall = useCallback(
    (direction: string) => suggest(entry.chrooked_id, direction),
    [suggest, entry.chrooked_id],
  );
  const applyCall = useApply(entry, renderer);

  const { state, open, setDirection, submit, editDraft, apply, reset } =
    useSuggest<Draft>({
      suggest: suggestCall,
      apply: applyCall,
      onApplied,
    });

  const { phase, direction, draft, rationale, alternatives, error, errorKind } =
    state;
  const applied = phase === "applied";
  const isLoading = phase === "loading";
  const isApplying = phase === "applying";

  // Tell the ledger whether this section currently has a proposal in flight so it
  // can auto-expand to a roomy layout (ac8 / P1). Any non-idle phase counts as
  // active; reset (Discard / Done) and unmount both report idle, restoring width.
  const isActive = phase !== "idle";
  useEffect(() => {
    onActiveChange?.(renderer.id, isActive);
    return () => onActiveChange?.(renderer.id, false);
  }, [onActiveChange, renderer.id, isActive]);

  // Focus the direction input the moment it opens (keyboard-first).
  const handleOpen = useCallback(() => {
    open();
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  const handleSubmit = useCallback(() => {
    if (direction.trim() === "" && phase === "input") return;
    void submit();
  }, [direction, phase, submit]);

  const idStem = `proposal-${renderer.id}`;
  const headingId = `${idStem}-heading`;

  // The cell grid (current │ proposed) is the renderer's job — the shell never
  // looks inside the draft.
  const cells = useMemo(
    () =>
      renderer.renderCells({
        entry,
        draft,
        rationale,
        onEdit: editDraft,
        applied,
      }),
    [renderer, entry, draft, rationale, editDraft, applied],
  );

  // The read-only body and the renderer's grid are mutually exclusive (pure
  // helper, guarded in suggestMachine.test): the read-only list shows under the
  // single heading until a proposal exists; once it does, the renderer's
  // current │ proposed grid IS the current column, so the read-only list hides
  // (no triplication — the BOUNCE 1 defect).
  const body = sectionBody(state);
  const showColumns = body === "columns";
  const showReadonly = body === "readonly";
  const canApply = phase === "proposed" && draft !== null;

  return (
    <section
      className="proposal proposal--section"
      aria-labelledby={headingId}
      data-phase={phase}
    >
      <div className="proposal__head">
        <h3 className="ledger__heading proposal__heading" id={headingId}>
          {renderer.title}
        </h3>
        {phase === "idle" && (
          <button
            type="button"
            id={`${idStem}-suggest`}
            className="proposal__suggest"
            onClick={handleOpen}
            aria-label={renderer.suggestLabel}
          >
            <span aria-hidden="true">✦</span> suggest
          </button>
        )}
        {isLoading && (
          <PokeballSpinner
            id={`${idStem}-spinner`}
            size={20}
            label="Proposing…"
          />
        )}
      </div>

      {showReadonly && children}

      {(phase === "input" || phase === "proposed" || phase === "error") && (
        <form
          className="proposal__direction"
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
        >
          <label className="proposal__direction-label" htmlFor={`${idStem}-direction`}>
            Direction
          </label>
          <input
            ref={inputRef}
            id={`${idStem}-direction`}
            className="proposal__direction-input"
            type="text"
            value={direction}
            placeholder={renderer.placeholder}
            onChange={(e) => setDirection(e.target.value)}
            autoComplete="off"
          />
          <button
            type="submit"
            id={`${idStem}-direction-submit`}
            className="proposal__direction-submit"
          >
            {phase === "proposed" ? "Re-suggest" : "Propose"}
          </button>
        </form>
      )}

      {error !== null && (
        <p
          className="proposal__error"
          id={`${idStem}-error`}
          role="alert"
        >
          <span className="proposal__error-tag mono" aria-hidden="true">
            {errorKind === "apply" ? "rejected" : "no proposal"}
          </span>
          {error}
          <span className="sr-only"> — nothing was written.</span>
        </p>
      )}

      {showColumns && (
        <div className="proposal__columns" data-applied={applied}>
          {cells}
        </div>
      )}

      {showColumns && (
        <Alternatives
          idStem={idStem}
          alternatives={alternatives}
          onSwap={(alt) => editDraft(renderer.applyAlternative(draft, alt))}
        />
      )}

      {(canApply || isApplying || applied) && (
        <div className="proposal__actions">
          {applied ? (
            <span className="proposal__applied mono" aria-live="polite">
              ✓ applied
            </span>
          ) : (
            <button
              type="button"
              id={`${idStem}-apply`}
              className="proposal__apply"
              disabled={!canApply || isApplying}
              onClick={() => void apply()}
            >
              {isApplying ? "Applying…" : `Apply ${renderer.title.toLowerCase()}`}
            </button>
          )}
          <button
            type="button"
            id={`${idStem}-dismiss`}
            className="proposal__dismiss"
            onClick={reset}
          >
            {applied ? "Done" : "Discard"}
          </button>
        </div>
      )}
    </section>
  );
}

interface AltProps {
  idStem: string;
  alternatives: { value: unknown; rationale: string }[];
  onSwap: (alt: { value: unknown; rationale: string }) => void;
}

/** The model's runner-up picks, revealed under the proposed column and swappable
    into the draft on click (Progressive Disclosure). */
function Alternatives({ idStem, alternatives, onSwap }: AltProps) {
  if (alternatives.length === 0) return null;
  return (
    <details className="proposal__alts" id={`${idStem}-alts`}>
      <summary className="proposal__alts-summary">
        Alternatives ({alternatives.length})
      </summary>
      <ul className="proposal__alts-list">
        {alternatives.map((alt, index) => (
          <li key={index} className="proposal__alt">
            <button
              type="button"
              id={`${idStem}-alt-${index}`}
              className="proposal__alt-swap"
              onClick={() => onSwap(alt)}
            >
              <span className="proposal__alt-value mono">
                {altLabel(alt.value)}
              </span>
              {alt.rationale && (
                <span className="proposal__alt-rationale">{alt.rationale}</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** A compact label for an alternative's value, whatever its section shape. */
function altLabel(value: unknown): string {
  if (typeof value === "string") return value;
  if (value !== null && typeof value === "object") {
    const v = value as Record<string, unknown>;
    if ("move" in v) {
      const level = "level" in v ? `L${String(v.level)} ` : "";
      return `${level}${String(v.move)}`;
    }
  }
  return String(value);
}
