/* CREATE NEW ability, driven through the EXISTING ability-create Seam
   (POST /api/abilities/suggest) — the same endpoint the chat skill uses (One
   Seam). Propose → preview (ability + behavior STUB + distribution) → confirm →
   write in order: PUT ability → PUT behavior → PUT species ×N. engine_hints is
   NEVER filled (the human's grounding pass); the STUB note is surfaced honestly;
   the server refuses to clobber an id collision (422, shown verbatim). Proposal-
   only fields (replaces/reasoning/ai_rating/warnings) are stripped before writes. */

import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { api, ApiError } from "../../api";
import type { DexEntry, SpeciesOverride } from "../../types";
import {
  makeoverApi,
  type AbilityCreateDraft,
  type AbilityCreateResponse,
  type StageFacts,
} from "../../lib/makeoverApi";
import type { StageActions } from "./StagePanel";

interface Props {
  entry: DexEntry;
  byId: ReadonlyMap<string, DexEntry>;
  redirectRef: RefObject<HTMLInputElement>;
  registerActions: (actions: StageActions | null) => void;
  onLocked: (facts: StageFacts, writtenIds?: string[]) => void;
}

type Phase = "input" | "proposing" | "proposed" | "writing" | "error";

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Unexpected error";
}

function seedOverride(species: string, byId: ReadonlyMap<string, DexEntry>): SpeciesOverride {
  const target = byId.get(species);
  return {
    name: target?.name ?? species,
    chrooked_id: species,
    aka: target?.dex != null ? { dex: target.dex } : {},
    types: null,
    abilities: null,
    stats: null,
    learnset: null,
    evolution: null,
  };
}

/** Write the created ability, its behavior stub, then each distribution species —
    in order, stop-and-report. Returns the species written (for the read-back). */
async function writeCreation(
  draft: AbilityCreateDraft,
  byId: ReadonlyMap<string, DexEntry>,
): Promise<string[]> {
  // 1. The owned ability (strip everything but the ability fields).
  await api.putAbility(draft.ability.chrooked_id, {
    name: draft.ability.name,
    chrooked_id: draft.ability.chrooked_id,
    description: draft.ability.description,
    aka: {},
  });
  // 2. The behavior stub AS-IS — engine_hints stays {} (never filled here).
  await api.putBehavior(draft.behavior.chrooked_id, draft.behavior);
  // 3. Distribute into the chosen slot on each species (merge, don't clobber
  //    other slots). Silent so the workbench flushes ONE dex refresh.
  const written: string[] = [];
  for (const row of draft.distribution) {
    let raw: SpeciesOverride;
    try {
      raw = await api.speciesOverride(row.species);
    } catch {
      raw = seedOverride(row.species, byId);
    }
    const current = byId.get(row.species)?.abilities ?? {
      primary: null,
      secondary: null,
      hidden: null,
    };
    await api.putSpecies(
      row.species,
      { ...raw, abilities: { ...current, [row.slot]: draft.ability.name } },
      undefined,
      { silent: true },
    );
    written.push(row.species);
  }
  return written;
}

export function AbilityCreatePanel({ entry, byId, redirectRef, registerActions, onLocked }: Props) {
  const [phase, setPhase] = useState<Phase>("input");
  const [direction, setDirection] = useState("");
  const [result, setResult] = useState<AbilityCreateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function propose() {
    if (direction.trim() === "") return;
    setPhase("proposing");
    setError(null);
    try {
      const response = await makeoverApi.createAbility(direction.trim());
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
        const written = await writeCreation(result.draft, byId);
        onLocked({ abilities: entry.abilities }, written);
      } catch (caught: unknown) {
        setError(
          `${messageOf(caught)} — partial writes may have landed (git is the undo).`,
        );
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

  return (
    <div className="mk-create" id="mk-ability-create" data-phase={phase}>
      <form
        className="mk-stage__redirect"
        onSubmit={(event) => {
          event.preventDefault();
          void propose();
        }}
      >
        <label className="mk-stage__redirect-label mono" htmlFor="mk-create-direction">
          new ability
        </label>
        <input
          ref={redirectRef}
          id="mk-create-direction"
          className="mk-stage__redirect-input mono"
          type="text"
          value={direction}
          placeholder="describe it (e.g. a Water sponge that boosts Speed when hit by Water)…"
          onChange={(event) => setDirection(event.target.value)}
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
          <span className="sr-only">Designing the ability…</span>
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

      {draft && (
        <div className="mk-create__preview">
          <section className="mk-create__ability">
            <h4 className="mk-create__ability-name">
              {draft.ability.name} <span className="mono mk-create__id">{draft.ability.chrooked_id}</span>
            </h4>
            <p className="mk-create__ability-desc">{draft.ability.description}</p>
            {result?.rationale.ai_rating && (
              <p className="mk-create__rating mono">AI rating · {result.rationale.ai_rating}</p>
            )}
          </section>

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

          {draft.distribution.length > 0 ? (
            <section className="mk-create__dist">
              <h5 className="mk-create__sub mono">distribution ({draft.distribution.length})</h5>
              <table className="mk-create__dist-table mono">
                <thead>
                  <tr>
                    <th scope="col">species</th>
                    <th scope="col">slot</th>
                    <th scope="col">replaces</th>
                  </tr>
                </thead>
                <tbody>
                  {draft.distribution.map((row) => (
                    <tr key={`${row.species}-${row.slot}`}>
                      <td>{byId.get(row.species)?.name ?? row.species}</td>
                      <td>{row.slot}</td>
                      <td>{row.replaces ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : (
            <p className="mk-empty mono">no species distribution — author now, distribute later.</p>
          )}

          <div className="mk-stage__actions">
            <button
              type="button"
              id="mk-create-confirm"
              className="mk-btn mk-btn--lock"
              disabled={phase === "writing"}
              onClick={() => confirmRef.current()}
            >
              {phase === "writing" ? "WRITING…" : "CREATE & DISTRIBUTE"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
