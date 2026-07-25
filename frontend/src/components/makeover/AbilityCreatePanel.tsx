/* CREATE NEW ability, driven through the EXISTING ability-create Seam
   (POST /api/abilities/suggest) — the same endpoint the chat skill uses (One
   Seam). Propose → preview (ability + behavior STUB + distribution) → confirm →
   write in order: PUT ability → PUT behavior → PUT species ×N. engine_hints is
   NEVER filled (the human's grounding pass); the STUB note is surfaced honestly;
   the server refuses to clobber an id collision (422, shown verbatim). Proposal-
   only fields (replaces/reasoning/ai_rating/warnings) are stripped before writes. */

import { useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { api, ApiError } from "../../api";
import type { DexEntry, SpeciesOverride } from "../../types";
import {
  makeoverApi,
  type AbilityCreateDraft,
  type AbilityCreateResponse,
  type StageFacts,
} from "../../lib/makeoverApi";
import { addRow, deriveReplaces, removeRow, setSlot, type DistRow } from "./distributionDraft";
import type { StageActions } from "./StagePanel";

const SLOTS: DistRow["slot"][] = ["primary", "secondary", "hidden"];

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
  // The editable distribution — seeded fresh each time a proposal lands (a TRY
  // AGAIN discards prior edits and re-seeds from the new proposal, per ac10).
  const [dist, setDist] = useState<DistRow[]>([]);
  const [addSpecies, setAddSpecies] = useState("");
  const [addSlot, setAddSlot] = useState<DistRow["slot"]>("primary");

  useEffect(() => {
    setDist(
      (result?.draft.distribution ?? []).map((row) => ({ species: row.species, slot: row.slot })),
    );
    setAddSpecies("");
    setAddSlot("primary");
  }, [result]);

  // Typed-name → chrooked_id resolver for the add-species datalist (the same
  // affordance the learnset RowEditor uses for moves, keyed on display name).
  const idByName = useMemo(() => {
    const map = new Map<string, string>();
    for (const member of byId.values()) map.set(member.name.toLowerCase(), member.chrooked_id);
    return map;
  }, [byId]);
  const resolvedAddId =
    idByName.get(addSpecies.trim().toLowerCase()) ??
    (byId.has(addSpecies.trim()) ? addSpecies.trim() : null);

  function commitAdd() {
    if (resolvedAddId === null) return;
    setDist((rows) => addRow(rows, { species: resolvedAddId, slot: addSlot }));
    setAddSpecies("");
  }

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
        // Write the EDITED distribution, not the proposal's — the author's slot
        // retargets, removals, and added species are what lands (ac10).
        const written = await writeCreation({ ...result.draft, distribution: dist }, byId);
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

          <section className="mk-create__dist" id="mk-create-dist">
            <h5 className="mk-create__sub mono">distribution ({dist.length})</h5>
            {dist.length > 0 ? (
              <table className="mk-create__dist-table mono">
                <thead>
                  <tr>
                    <th scope="col">species</th>
                    <th scope="col">slot</th>
                    <th scope="col">replaces</th>
                    <th scope="col">
                      <span className="sr-only">remove</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {dist.map((row, index) => {
                    const label = byId.get(row.species)?.name ?? row.species;
                    const replaces = deriveReplaces(byId, row.species, row.slot);
                    return (
                      <tr key={row.species} id={`mk-dist-row-${row.species}`}>
                        <td>{label}</td>
                        <td>
                          <select
                            className="mk-select mono"
                            aria-label={`${label} slot`}
                            value={row.slot}
                            onChange={(event) =>
                              setDist((rows) =>
                                setSlot(rows, index, event.target.value as DistRow["slot"]),
                              )
                            }
                          >
                            {SLOTS.map((slot) => (
                              <option key={slot} value={slot}>
                                {slot}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td>{replaces ?? "—"}</td>
                        <td>
                          <button
                            type="button"
                            className="mk-lrow__remove mono"
                            aria-label={`Remove ${label} from the distribution`}
                            title={`Remove ${label}`}
                            onClick={() => setDist((rows) => removeRow(rows, index))}
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <p className="mk-empty mono">
                no species yet — add one below, or author now and distribute later.
              </p>
            )}

            <div className="mk-dist-add" id="mk-dist-add">
              <input
                className="mk-stage__redirect-input mono"
                id="mk-dist-add-species"
                type="text"
                list="mk-dist-species-list"
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
              <datalist id="mk-dist-species-list">
                {[...byId.values()].map((member) => (
                  <option key={member.chrooked_id} value={member.name} />
                ))}
              </datalist>
              <select
                className="mk-select mono"
                aria-label="Slot for the added species"
                value={addSlot}
                onChange={(event) => setAddSlot(event.target.value as DistRow["slot"])}
              >
                {SLOTS.map((slot) => (
                  <option key={slot} value={slot}>
                    {slot}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="mk-btn mk-btn--ghost"
                id="mk-dist-add-btn"
                disabled={resolvedAddId === null}
                title={resolvedAddId === null ? "Type a known species name" : "Add to distribution"}
                onClick={commitAdd}
              >
                ADD
              </button>
            </div>
          </section>

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
