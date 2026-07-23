/* The MIRROR step — the mirror-only journey (ac8). When no design stage is
   selected, the workbench lands here: preview the final evo's CURRENT kit (types
   + abilities + learnset − L0) copied onto its pre-evos, then LOCK IN writes ONLY
   the pre-evos (the final evo's own fields are never touched). Reuses
   mirrorDownPreview + the shared writeMirror helper; the tail follows. */

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../../api";
import type { DexEntry } from "../../types";
import type { StageFacts } from "../../lib/makeoverApi";
import { mirrorDownPreview, preEvos } from "../../lib/mirrorDown";
import { writeMirror } from "./mirrorWrite";
import type { StageActions } from "./StagePanel";

interface Props {
  entry: DexEntry;
  byId: ReadonlyMap<string, DexEntry>;
  registerActions: (actions: StageActions | null) => void;
  onLocked: (facts: StageFacts, writtenIds?: string[]) => void;
}

type Phase = "ready" | "writing" | "error";

export function MirrorStage({ entry, byId, registerActions, onLocked }: Props) {
  const [phase, setPhase] = useState<Phase>("ready");
  const [error, setError] = useState<string | null>(null);

  const rows = useMemo(
    () =>
      mirrorDownPreview(entry, byId, {
        types: entry.types,
        abilities: entry.abilities,
        learnset: entry.learnset,
      }),
    [entry, byId],
  );
  const hasLine = preEvos(entry, byId).length > 0;

  const writeRef = useRef<() => void>(() => {});
  writeRef.current = () => {
    if (phase === "writing" || !hasLine) return;
    void (async () => {
      setPhase("writing");
      setError(null);
      try {
        const written = await writeMirror(rows);
        onLocked({}, written);
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
    })();
  };

  useEffect(() => {
    registerActions({
      lockIn: () => writeRef.current(),
      focusRedirect: () => undefined,
      canLock: hasLine && phase !== "writing",
      phase,
    });
    return () => registerActions(null);
  }, [registerActions, hasLine, phase]);

  return (
    <div className="mk-stage" data-phase={phase} id="mk-stage-mirror">
      <p className="mk-direction__lead">
        Mirror <strong>{entry.name}</strong>'s current kit onto its pre-evolutions — same typing +
        abilities, learnset minus the L0 on-evolution rows. The final evo is left untouched.
      </p>

      {!hasLine && <p className="mk-empty mono">no pre-evolutions to mirror to.</p>}

      {hasLine && (
        <ul className="mk-mirror__list" id="mk-mirror-only-list">
          {rows.map((row) => (
            <li key={row.chrooked_id} className="mk-mirror__row">
              <span className="mk-mirror__name">{row.name}</span>
              <span className="mono mk-mirror__count">
                {row.types.join("/")} · {row.learnset.length} moves
                {row.strippedL0.length > 0 && ` · −L0: ${row.strippedL0.join(", ")}`}
              </span>
            </li>
          ))}
        </ul>
      )}

      {error !== null && (
        <p className="mk-stage__error" role="alert">
          <span className="mk-stage__error-tag mono" aria-hidden="true">
            rejected
          </span>
          {error}
        </p>
      )}

      {hasLine && (
        <div className="mk-stage__actions">
          <button
            type="button"
            id="mk-mirror-lock"
            className="mk-btn mk-btn--lock"
            disabled={phase === "writing"}
            onClick={() => writeRef.current()}
          >
            {phase === "writing" ? "WRITING…" : "LOCK IN"}
          </button>
        </div>
      )}
    </div>
  );
}
