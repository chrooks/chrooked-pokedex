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
import { MirrorRowList } from "./MirrorRowList";
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
  const [excluded, setExcluded] = useState<ReadonlySet<string>>(new Set());

  const rows = useMemo(
    () =>
      mirrorDownPreview(entry, byId, {
        types: entry.types,
        abilities: entry.abilities,
        learnset: entry.learnset,
      }),
    [entry, byId],
  );
  const included = useMemo(
    () => rows.filter((row) => !excluded.has(row.chrooked_id)),
    [rows, excluded],
  );
  const hasLine = preEvos(entry, byId).length > 0;
  // Nothing to lock if every pre-evo is skipped.
  const canWrite = included.length > 0;

  function toggle(chrookedId: string) {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(chrookedId)) next.delete(chrookedId);
      else next.add(chrookedId);
      return next;
    });
  }

  const writeRef = useRef<() => void>(() => {});
  writeRef.current = () => {
    if (phase === "writing" || !hasLine || !canWrite) return;
    void (async () => {
      setPhase("writing");
      setError(null);
      try {
        const written = await writeMirror(included);
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
      canLock: hasLine && canWrite && phase !== "writing",
      phase,
    });
    return () => registerActions(null);
  }, [registerActions, hasLine, canWrite, phase]);

  return (
    <div className="mk-stage" data-phase={phase} id="mk-stage-mirror">
      <p className="mk-direction__lead">
        Mirror <strong>{entry.name}</strong>'s current kit onto its pre-evolutions — same typing +
        abilities, learnset minus the L0 on-evolution rows. The final evo is left untouched.
      </p>

      {!hasLine && <p className="mk-empty mono">no pre-evolutions to mirror to.</p>}

      {hasLine && (
        <MirrorRowList
          rows={rows}
          excluded={excluded}
          onToggle={toggle}
          id="mk-mirror-only-list"
        />
      )}
      {hasLine && !canWrite && (
        <p className="mk-empty mono">every pre-evo skipped — nothing to mirror.</p>
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
            disabled={phase === "writing" || !canWrite}
            onClick={() => writeRef.current()}
          >
            {phase === "writing" ? "WRITING…" : "LOCK IN"}
          </button>
        </div>
      )}
    </div>
  );
}
