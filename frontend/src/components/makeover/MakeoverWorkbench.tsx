/* The Makeover Workbench — a full-screen takeover inside the device frame. Three
   columns: the stage rail (left, the à la carte picker), the active stage
   (center), the line strip (right). À la carte (ac8): the rail toggles which
   design facets this session touches. The heartbeat is propose → tweak → LOCK IN
   per selected stage; with nothing selected it is the mirror-only journey; after
   the last lock the tail runs automatically (apply → proof → log). The Ruleset +
   this session's toggles drive progression, so a reload resumes on the first
   unlocked selected stage and Back returns to the dex exactly as left (ac1).

   Keyboard path (ac7/ac8): Enter = LOCK IN, t = focus redirect, space = toggle a
   focused rail stage (native button), Esc = abandon. ArrowUp/Down + e (row focus /
   edit) live inside the learnset stage where the rows are. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DexEntry, Move, Target } from "../../types";
import {
  defaultSelected,
  firstUnlocked,
  resolveActiveStage,
  toggleSelected,
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
import { MirrorStage } from "./MirrorStage";
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
  // The à la carte selection — seeded once from the Ruleset (smart defaults), then
  // toggled by the rail. Session state: a lock+reload does not reset it (the same
  // mount), but a fresh page reload re-derives (resume).
  const [selected, setSelected] = useState<Set<DesignStage>>(() =>
    defaultSelected(entry.overridden_fields),
  );
  const [sessionLocked, setSessionLocked] = useState<Set<Stage>>(new Set());
  const [writtenIds, setWrittenIds] = useState<Set<string>>(new Set());
  const [direction, setDirection] = useState("");
  const [corrections, setCorrections] = useState<string[]>([]);
  const [facts, setFacts] = useState<StageFacts>({});
  const [rubric, setRubric] = useState<LearnsetRubric | null>(null);

  const redirectRef = useRef<HTMLInputElement>(null);
  const actionsRef = useRef<StageActions | null>(null);

  const byId = useMemo(() => new Map(allEntries.map((e) => [e.chrooked_id, e])), [allEntries]);
  const linePre = useMemo(() => preEvos(entry, byId), [entry, byId]);
  const movePower = useMemo(() => {
    const map = new Map<string, number | null>();
    for (const move of moves) map.set(move.name, move.power);
    return map;
  }, [moves]);

  const active = resolveActiveStage(stage, selected, sessionLocked);

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

  const handleNavigate = useCallback((target: Stage) => onStage(target), [onStage]);

  const handleToggle = useCallback((toggled: DesignStage) => {
    setSelected((prev) => toggleSelected(prev, toggled));
  }, []);

  const handleDirectionChosen = useCallback(
    (chosen: string) => {
      const nextLocked = new Set(sessionLocked).add("direction");
      setDirection(chosen);
      setSessionLocked(nextLocked);
      onStage(firstUnlocked(selected, nextLocked));
    },
    [selected, sessionLocked, onStage],
  );

  const handleLocked = useCallback(
    (nextFacts: StageFacts, ids?: string[]) => {
      setFacts((prev) => ({ ...prev, ...nextFacts }));
      setWrittenIds((prev) => new Set([...prev, ...(ids ?? [entry.chrooked_id])]));
      const nextLocked = new Set(sessionLocked).add(active);
      setSessionLocked(nextLocked);
      onStage(firstUnlocked(selected, nextLocked));
      onSaved();
    },
    [active, selected, sessionLocked, entry.chrooked_id, onStage, onSaved],
  );

  // Global keyboard path. Enter = LOCK IN, t = focus redirect, Esc = abandon.
  // Skipped inside form fields AND on focused buttons (a rail button handles its
  // own Enter/space natively — space toggles it), except Escape which always
  // unwinds.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const inControl =
        target !== null &&
        (target.tagName === "INPUT" ||
          target.tagName === "SELECT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "BUTTON" ||
          target.isContentEditable);
      if (event.key === "Escape") {
        event.preventDefault();
        onExit();
        return;
      }
      if (inControl || event.metaKey || event.ctrlKey || event.altKey) return;
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
  }, [onExit]);

  const commonProps: CommonStageProps = {
    entry,
    initialDirection: direction,
    canLock: true,
    redirectRef,
    registerActions,
    onLocked: handleLocked,
    onRedirect: handleRedirect,
  };

  const targetId = activeTargetId ?? targets[0]?.id ?? null;
  const targetLabel = targets.find((t) => t.id === targetId)?.label ?? null;
  const changedIds = writtenIds.size > 0 ? [...writtenIds] : [entry.chrooked_id];

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
      panel = <AbilitiesStage {...commonProps} abilityOptions={abilityOptions} byId={byId} />;
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
    case "mirror":
      panel = (
        <MirrorStage
          entry={entry}
          byId={byId}
          registerActions={registerActions}
          onLocked={handleLocked}
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
          changedIds={changedIds}
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
    <div className="mk-workbench" id="makeover-workbench">
      <header className="mk-workbench__head">
        <button type="button" className="mk-workbench__exit mono" onClick={onExit} aria-label="Close makeover (Esc)">
          ← dex
        </button>
        <h2 className="mk-workbench__title">
          makeover · <strong>{entry.name}</strong>
        </h2>
      </header>
      <div className="mk-workbench__body">
        <StageRail
          selected={selected}
          sessionLocked={sessionLocked}
          active={active}
          onNavigate={handleNavigate}
          onToggle={handleToggle}
        />
        <main className="mk-workbench__stage" aria-live="polite">
          {panel}
        </main>
        <LineStrip
          anchor={entry}
          preEvos={linePre}
          facts={facts}
          lockedLearnset={sessionLocked.has("learnset") || sessionLocked.has("mirror")}
          backdropTargetId={backdropTargetId}
        />
      </div>
    </div>
  );
}
