/* The MIRROR wizard — a standing stop in EVERY makeover journey, after the last
   design lock and before the auto tail (also reachable directly: the profile's
   Mirror button, or a workbench with zero design stages selected). Pick the
   ANCHOR (any member of the evolution line), the FACETS to copy (typing / stats /
   abilities / learnset − L0), and the RECIPIENTS (any other line member; the
   anchor's pre-evos start included, evolved stages start skipped). LOCK IN
   writes ONLY the recipients — the anchor is never touched. With nothing to
   write (no line, every recipient skipped, or no facet picked) the button
   becomes SKIP and the flow continues to the tail. Stats is opt-in: the line
   default SCALES stats rather than copying them (CLAUDE.md), so mirroring them
   verbatim is a deliberate exception. */

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../../api";
import type { DexEntry } from "../../types";
import type { StageFacts } from "../../lib/makeoverApi";
import {
  DEFAULT_MIRROR_FACETS,
  MIRROR_FACETS,
  lineMembers,
  mirrorRows,
  type MirrorFacet,
} from "../../lib/mirrorDown";
import { writeMirror } from "./mirrorWrite";
import { MirrorRowList } from "./MirrorRowList";
import { PokeballSpinner } from "../PokeballSpinner";
import type { StageActions } from "./StagePanel";

interface Props {
  entry: DexEntry;
  byId: ReadonlyMap<string, DexEntry>;
  registerActions: (actions: StageActions | null) => void;
  onLocked: (facts: StageFacts, writtenIds?: string[]) => void;
}

type Phase = "ready" | "writing" | "error";

const FACET_LABEL: Record<MirrorFacet, string> = {
  types: "typing",
  stats: "stats",
  abilities: "abilities",
  learnset: "learnset − L0",
};

export function MirrorStage({ entry, byId, registerActions, onLocked }: Props) {
  const [phase, setPhase] = useState<Phase>("ready");
  const [error, setError] = useState<string | null>(null);

  const line = useMemo(() => lineMembers(entry, byId), [entry, byId]);
  const [anchorId, setAnchorId] = useState(entry.chrooked_id);
  const anchor =
    line.find((member) => member.chrooked_id === anchorId) ?? entry;

  const [facets, setFacets] = useState<ReadonlySet<MirrorFacet>>(
    DEFAULT_MIRROR_FACETS,
  );
  // Evolved stages (relative to the anchor) start skipped: mirroring UP is
  // allowed but deliberate. Positional (line is base→tip ordered) rather than a
  // second graph walk, so a branch stopping the walk can't miss a skip.
  const laterThan = (id: string): Set<string> => {
    const index = line.findIndex((member) => member.chrooked_id === id);
    return new Set(
      line.filter((_, i) => i > index).map((member) => member.chrooked_id),
    );
  };
  const [excluded, setExcluded] = useState<ReadonlySet<string>>(() =>
    laterThan(entry.chrooked_id),
  );

  const recipients = useMemo(
    () => line.filter((member) => member.chrooked_id !== anchor.chrooked_id),
    [line, anchor.chrooked_id],
  );
  const rows = useMemo(
    () =>
      mirrorRows(
        {
          types: anchor.types,
          abilities: anchor.abilities,
          stats: anchor.stats,
          learnset: anchor.learnset,
        },
        recipients,
      ),
    [anchor, recipients],
  );
  const included = useMemo(
    () => rows.filter((row) => !excluded.has(row.chrooked_id)),
    [rows, excluded],
  );
  const hasLine = line.length > 1;
  // Nothing selected to write → the lock becomes a SKIP (the stage never blocks
  // the tail; a species with no line just passes through).
  const canWrite = hasLine && included.length > 0 && facets.size > 0;

  function pickAnchor(nextId: string) {
    setAnchorId(nextId);
    setExcluded(laterThan(nextId));
  }

  function toggleFacet(facet: MirrorFacet) {
    setFacets((prev) => {
      const next = new Set(prev);
      if (next.has(facet)) next.delete(facet);
      else next.add(facet);
      return next;
    });
  }

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
    if (phase === "writing") return;
    if (!canWrite) {
      // SKIP: nothing to mirror — lock the stage with zero writes.
      onLocked({}, []);
      return;
    }
    void (async () => {
      setPhase("writing");
      setError(null);
      try {
        const written = await writeMirror(included, facets);
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
      canLock: phase !== "writing",
      phase,
    });
    return () => registerActions(null);
  }, [registerActions, phase]);

  return (
    <div className="mk-stage" data-phase={phase} id="mk-stage-mirror">
      <p className="mk-direction__lead">
        Mirror <strong>{anchor.name}</strong>'s current kit onto the rest of its
        line. Pick the anchor, the facets, and the recipients — the anchor itself
        is never touched.
      </p>

      {!hasLine && (
        <p className="mk-empty mono">no evolution line to mirror across — skip ahead.</p>
      )}

      {hasLine && (
        <div className="mk-mirror__controls">
          <label className="mk-mirror__anchor mono" htmlFor="mk-mirror-anchor">
            anchor
            <select
              id="mk-mirror-anchor"
              className="mk-select"
              value={anchor.chrooked_id}
              onChange={(e) => pickAnchor(e.target.value)}
            >
              {line.map((member) => (
                <option key={member.chrooked_id} value={member.chrooked_id}>
                  {member.name}
                </option>
              ))}
            </select>
          </label>

          <fieldset className="mk-mirror__facets" id="mk-mirror-facets">
            <legend className="mono">facets</legend>
            {MIRROR_FACETS.map((facet) => (
              <label key={facet} className="mk-mirror__facet mono">
                <input
                  type="checkbox"
                  id={`mk-mirror-facet-${facet}`}
                  checked={facets.has(facet)}
                  onChange={() => toggleFacet(facet)}
                />
                {FACET_LABEL[facet]}
              </label>
            ))}
            {facets.has("stats") && (
              <p className="mk-mirror__facet-note mono">
                stats copy verbatim — the line default scales them instead.
              </p>
            )}
          </fieldset>
        </div>
      )}

      {hasLine && (
        <MirrorRowList
          rows={rows}
          excluded={excluded}
          onToggle={toggle}
          facets={facets}
          id="mk-mirror-only-list"
        />
      )}
      {hasLine && included.length === 0 && (
        <p className="mk-empty mono">every recipient skipped — nothing to mirror.</p>
      )}
      {hasLine && facets.size === 0 && (
        <p className="mk-empty mono">no facet picked — nothing to mirror.</p>
      )}

      {error !== null && (
        <p className="mk-stage__error" role="alert">
          <span className="mk-stage__error-tag mono" aria-hidden="true">
            rejected
          </span>
          {error}
        </p>
      )}

      <div className="mk-stage__actions">
        <button
          type="button"
          id="mk-mirror-lock"
          className="mk-btn mk-btn--lock"
          disabled={phase === "writing"}
          onClick={() => writeRef.current()}
        >
          {phase === "writing" ? "WRITING…" : canWrite ? "LOCK IN" : "SKIP →"}
        </button>
        {phase === "writing" && (
          <PokeballSpinner
            id="mk-mirror-spinner"
            size={20}
            label="Writing the recipients…"
          />
        )}
      </div>
    </div>
  );
}
