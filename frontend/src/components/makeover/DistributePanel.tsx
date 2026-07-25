/* DISTRIBUTE an EXISTING ability onto species — the ac10 distribution editor
   surfaced as its own reachable step (not only the tail of ability-create). Pick a
   known ability, add species + slots, CONFIRM writes each slot through the existing
   species CRUD route (read-merge-write, other slots preserved). Reuses the pure
   distributionDraft ops and the shared writeDistribution.

   ponytail: the rows/add-species table markup overlaps the ability-create panel's;
   kept separate rather than extracting a shared table so the working create panel
   stays untouched. Extract a DistributionTable if a third caller appears. */

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../../api";
import type { DexEntry } from "../../types";
import { addRow, deriveReplaces, removeRow, setSlot, type DistRow } from "./distributionDraft";
import { writeDistribution } from "./distributionWrite";
import type { StageActions } from "./StagePanel";

const SLOTS: DistRow["slot"][] = ["primary", "secondary", "hidden"];

interface Props {
  byId: ReadonlyMap<string, DexEntry>;
  abilityOptions: readonly string[];
  registerActions: (actions: StageActions | null) => void;
  /** Refresh the dex after the distribution lands (a side write — it does NOT lock
      the abilities design stage). */
  onSaved: () => void;
  /** Return to the host stage after a write or CANCEL. */
  onClose: () => void;
}

type Phase = "input" | "writing" | "error";

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Unexpected error";
}

export function DistributePanel({ byId, abilityOptions, registerActions, onSaved, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("input");
  const [ability, setAbility] = useState("");
  const [dist, setDist] = useState<DistRow[]>([]);
  const [addSpecies, setAddSpecies] = useState("");
  const [addSlot, setAddSlot] = useState<DistRow["slot"]>("primary");
  const [error, setError] = useState<string | null>(null);
  const abilityRef = useRef<HTMLInputElement>(null);

  const knownAbility = ability.trim() !== "" && abilityOptions.includes(ability.trim());

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

  const canConfirm = knownAbility && dist.length > 0;

  const confirmRef = useRef<() => void>(() => {});
  confirmRef.current = () => {
    if (!canConfirm) return;
    void (async () => {
      setPhase("writing");
      setError(null);
      try {
        await writeDistribution(ability.trim(), dist, byId);
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
      focusRedirect: () => abilityRef.current?.focus(),
      canLock: canConfirm,
      phase,
    });
    return () => registerActions(null);
  }, [registerActions, canConfirm, phase]);

  return (
    <div className="mk-create" id="mk-distribute" data-phase={phase}>
      <div className="mk-stage__redirect">
        <label className="mk-stage__redirect-label mono" htmlFor="mk-distribute-ability">
          ability
        </label>
        <input
          ref={abilityRef}
          id="mk-distribute-ability"
          className="mk-stage__redirect-input mono"
          type="text"
          list="mk-distribute-ability-list"
          value={ability}
          placeholder="pick an existing ability to distribute…"
          onChange={(event) => setAbility(event.target.value)}
          autoComplete="off"
        />
        <datalist id="mk-distribute-ability-list">
          {abilityOptions.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </div>

      {error !== null && (
        <p className="mk-stage__error" role="alert">
          <span className="mk-stage__error-tag mono" aria-hidden="true">
            rejected
          </span>
          {error}
        </p>
      )}

      <section className="mk-create__dist" id="mk-distribute-dist">
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
                  <tr key={row.species} id={`mk-distribute-row-${row.species}`}>
                    <td>{label}</td>
                    <td>
                      <select
                        className="mk-select mono"
                        aria-label={`${label} slot`}
                        value={row.slot}
                        onChange={(event) =>
                          setDist((rows) => setSlot(rows, index, event.target.value as DistRow["slot"]))
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
          <p className="mk-empty mono">no species yet — add one below.</p>
        )}

        <div className="mk-dist-add" id="mk-distribute-add">
          <input
            className="mk-stage__redirect-input mono"
            id="mk-distribute-add-species"
            type="text"
            list="mk-distribute-species-list"
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
          <datalist id="mk-distribute-species-list">
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
            id="mk-distribute-add-btn"
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
          className="mk-btn mk-btn--ghost mono"
          onClick={onClose}
          disabled={phase === "writing"}
        >
          CANCEL
        </button>
        <button
          type="button"
          id="mk-distribute-confirm"
          className="mk-btn mk-btn--lock"
          disabled={!canConfirm || phase === "writing"}
          title={canConfirm ? "Distribute this ability" : "Pick an ability and at least one species"}
          onClick={() => confirmRef.current()}
        >
          {phase === "writing" ? "WRITING…" : "DISTRIBUTE"}
        </button>
      </div>
    </div>
  );
}
