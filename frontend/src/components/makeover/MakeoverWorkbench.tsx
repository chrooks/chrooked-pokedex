/* The Makeover Workbench — a full-screen takeover inside the device frame. Three
   columns: the stage rail (left), the active stage (center), the line strip
   (right). The heartbeat is propose → tweak → LOCK IN per design stage; after the
   last design lock the tail runs automatically (apply → proof → log). The Ruleset
   is the source of truth for progression, so a reload resumes on the first
   unlocked stage and Back returns to the dex exactly as left (ac1).

   Keyboard path (ac7): Enter = LOCK IN, t = focus redirect, Esc = back/abandon.
   ArrowUp/Down + e (row focus / edit) are handled inside the learnset stage where
   the rows live. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DexEntry, Move, Target } from "../../types";
import {
  isDesignStage,
  lockedFromFields,
  nextStage,
  prevStage,
  resolveActiveStage,
  type DesignStage,
  type Stage,
} from "../../lib/makeoverStages";
import { makeoverApi, type StageFacts } from "../../lib/makeoverApi";
import type { LearnsetRubric } from "../../lib/learnsetBands";
import { preEvos } from "../../lib/mirrorDown";
import { StageRail } from "./StageRail";
import { LineStrip } from "./LineStrip";
import { DirectionStage } from "./DirectionStage";
import { TypingStage } from "./TypingStage";
import { StatsStage } from "./StatsStage";
import { AbilitiesStage } from "./AbilitiesStage";
import { LearnsetStage } from "./LearnsetStage";
import { AutoTail } from "./AutoTail";
import type { StageActions } from "./StagePanel";
import type { CommonStageProps } from "./stageProps";
import "./makeover.css";

interface Props {
  entry: DexEntry;
  allEntries: DexEntry[];
  moves: readonly Move[];
  stage: Stage | null;
  onStage: (stage: Stage | null) => void;
  onExit: () => void;
  onSaved: () => void;
  moveOptions: readonly string[];
  abilityOptions: readonly string[];
  targets: readonly Target[];
  activeTargetId: string | null;
  backdropTargetId?: string | null;
}

export function MakeoverWorkbench({
  entry,
  allEntries,
  moves,
  stage,
  onStage,
  onExit,
  onSaved,
  moveOptions,
  abilityOptions,
  targets,
  activeTargetId,
  backdropTargetId,
}: Props) {
  const [sessionLocked, setSessionLocked] = useState<Set<DesignStage>>(new Set());
  const [direction, setDirection] = useState("");
  const [corrections, setCorrections] = useState<string[]>([]);
  const [facts, setFacts] = useState<StageFacts>({});
  const [rubric, setRubric] = useState<LearnsetRubric | null>(null);

  const redirectRef = useRef<HTMLInputElement>(null);
  const actionsRef = useRef<StageActions | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const byId = useMemo(() => new Map(allEntries.map((e) => [e.chrooked_id, e])), [allEntries]);
  const linePre = useMemo(() => preEvos(entry, byId), [entry, byId]);
  const movePower = useMemo(() => {
    const map = new Map<string, number | null>();
    for (const move of moves) map.set(move.name, move.power);
    return map;
  }, [moves]);

  // Progression: the Ruleset (the species' overridden fields) plus this session's
  // optimistic locks (direction has no field; a just-locked stage before the dex
  // refetch lands). Resume derives from the Ruleset alone.
  const locked = useMemo(() => {
    const set = lockedFromFields(entry.overridden_fields);
    for (const s of sessionLocked) set.add(s);
    return set;
  }, [entry.overridden_fields, sessionLocked]);

  const active = resolveActiveStage(stage, locked);

  // Fetch the pacing-band rubric once (single source of truth; annotates learnset
  // rows). A failure leaves it null → rows simply render without band flags.
  useEffect(() => {
    const controller = new AbortController();
    makeoverApi
      .learnsetRubric(controller.signal)
      .then((data) => !controller.signal.aborted && setRubric(data))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const registerActions = useCallback((actions: StageActions | null) => {
    actionsRef.current = actions;
  }, []);

  const handleRedirect = useCallback((text: string) => {
    setCorrections((prev) => [...prev, text]);
  }, []);

  const handleNavigate = useCallback(
    (target: Stage) => {
      onStage(target);
    },
    [onStage],
  );

  const handleDirectionChosen = useCallback(
    (chosen: string) => {
      setDirection(chosen);
      setSessionLocked((prev) => new Set(prev).add("direction"));
      onStage("typing");
    },
    [onStage],
  );

  const handleLocked = useCallback(
    (nextFacts: StageFacts) => {
      setFacts((prev) => ({ ...prev, ...nextFacts }));
      if (isDesignStage(active)) {
        setSessionLocked((prev) => new Set(prev).add(active));
        onStage(nextStage(active));
      }
      onSaved();
    },
    [active, onStage, onSaved],
  );

  const handleEscape = useCallback(() => {
    if (isDesignStage(active) && active !== "direction") {
      onStage(prevStage(active));
      return;
    }
    onExit();
  }, [active, onStage, onExit]);

  // Global keyboard path. Enter = LOCK IN, t = focus redirect, Esc = back/abandon.
  // Skipped inside form fields (so typing a redirect / editing a row is unhurt),
  // except Escape which always unwinds.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const inField =
        target !== null &&
        (target.tagName === "INPUT" ||
          target.tagName === "SELECT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (event.key === "Escape") {
        event.preventDefault();
        handleEscape();
        return;
      }
      if (inField || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "Enter") {
        if (actionsRef.current?.canLock) {
          event.preventDefault();
          actionsRef.current.lockIn();
        }
      } else if (event.key === "t" || event.key === "T") {
        event.preventDefault();
        actionsRef.current?.focusRedirect();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleEscape]);

  const commonProps: CommonStageProps = {
    entry,
    initialDirection: direction,
    canLock: isDesignStage(active) ? true : false,
    redirectRef,
    registerActions,
    onLocked: handleLocked,
    onRedirect: handleRedirect,
  };

  const targetId = activeTargetId ?? targets[0]?.id ?? null;
  const targetLabel = targets.find((t) => t.id === targetId)?.label ?? null;

  let panel: React.ReactNode;
  switch (active) {
    case "direction":
      panel = (
        <DirectionStage
          entry={entry}
          redirectRef={redirectRef}
          registerActions={registerActions}
          onChosen={handleDirectionChosen}
        />
      );
      break;
    case "typing":
      panel = <TypingStage {...commonProps} />;
      break;
    case "stats":
      panel = <StatsStage {...commonProps} />;
      break;
    case "abilities":
      panel = <AbilitiesStage {...commonProps} abilityOptions={abilityOptions} />;
      break;
    case "learnset":
      panel = (
        <LearnsetStage
          {...commonProps}
          moveOptions={moveOptions}
          movePower={movePower}
          rubric={rubric}
          byId={byId}
        />
      );
      break;
    case "done":
      panel = (
        <div className="mk-done" id="mk-done-view">
          <p className="mk-done__headline mono">makeover complete</p>
          <button type="button" className="mk-btn mk-btn--lock" onClick={onExit}>
            BACK TO DEX
          </button>
        </div>
      );
      break;
    default:
      panel = (
        <AutoTail
          anchorName={entry.name}
          changedIds={[entry.chrooked_id, ...linePre.map((m) => m.chrooked_id)]}
          targetId={targetId}
          targetLabel={targetLabel}
          direction={direction}
          corrections={corrections}
          onStage={(sub) => onStage(sub)}
          onDone={onExit}
        />
      );
  }

  return (
    <div className="mk-workbench" id="makeover-workbench" ref={rootRef}>
      <header className="mk-workbench__head">
        <button type="button" className="mk-workbench__exit mono" onClick={onExit} aria-label="Close makeover (Esc)">
          ← dex
        </button>
        <h2 className="mk-workbench__title">
          makeover · <strong>{entry.name}</strong>
        </h2>
      </header>
      <div className="mk-workbench__body">
        <StageRail locked={locked} active={active} onNavigate={handleNavigate} />
        <main className="mk-workbench__stage" aria-live="polite">
          {panel}
        </main>
        <LineStrip
          anchor={entry}
          preEvos={linePre}
          facts={facts}
          lockedLearnset={locked.has("learnset")}
          backdropTargetId={backdropTargetId}
        />
      </div>
    </div>
  );
}
