/* The Makeover Workbench — a full-screen takeover inside the device frame. Three
   columns: the stage rail (left, the à la carte picker), the active stage
   (center), the line strip (right). À la carte (ac8): the rail toggles which
   design facets this session touches. The heartbeat is propose → tweak → LOCK IN
   per selected stage; with nothing selected it is the mirror-only journey; after
   the last lock the tail runs automatically (apply → proof → log). The Ruleset +
   this session's toggles drive progression, so a reload resumes on the first
   unlocked selected stage and Back returns to the dex exactly as left (ac1).

   Keyboard path (ac7/ac8): Enter = LOCK IN, t = focus redirect, space = toggle a
   focused rail stage (native button), Esc = park (back to the dex, draft kept). ArrowUp/Down + e (row focus /
   edit) live inside the learnset stage where the rows are. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DexEntry, Move, Target } from "../../types";
import {
  defaultSelected,
  facetSummary,
  firstUnlocked,
  resolveActiveStage,
  toggleSelected,
  type DesignStage,
  type Stage,
} from "../../lib/makeoverStages";
import { makeoverApi, type StageFacts } from "../../lib/makeoverApi";
import type { LearnsetRubric } from "../../lib/learnsetBands";
import { preEvos } from "../../lib/mirrorDown";
import { attackCategory } from "../../lib/moveDisplay";
import { snapshotProfile } from "../../lib/profileDiff";
import { StageRail } from "./StageRail";
import { OverheadRail } from "./OverheadRail";
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
  /** An explicit à-la-carte seed (a profile section's suggest deep link), or
      null/undefined for the Ruleset-derived smart defaults. Seed-only: rail
      toggles after entry stay session state. */
  initialSelected?: readonly DesignStage[] | null;
  onStage: (stage: Stage | null) => void;
  /** True while the workbench is parked (mounted but hidden behind the dex) — the
      global keyboard path stands down so Esc/Enter/t belong to the dex. */
  paused?: boolean;
  /** Dismiss without abandoning — "← dex"/Esc. The workbench stays mounted, so an
      unlocked draft survives a trip to the dex (look a move up mid-edit). */
  onPark: () => void;
  /** Leave for good (the finished run) — the workbench unmounts. */
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
  initialSelected,
  onStage,
  paused = false,
  onPark,
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
  // An explicit deep-link seed wins over the smart defaults — including the
  // EMPTY seed, which is the mirror-only journey ("Mirror" on a profile).
  const [selected, setSelected] = useState<Set<DesignStage>>(() =>
    initialSelected != null
      ? new Set(initialSelected)
      : defaultSelected(entry.overridden_fields),
  );
  const [sessionLocked, setSessionLocked] = useState<Set<Stage>>(new Set());
  const [writtenIds, setWrittenIds] = useState<Set<string>>(new Set());
  const [direction, setDirection] = useState("");
  const [corrections, setCorrections] = useState<string[]>([]);
  const [facts, setFacts] = useState<StageFacts>({});
  const [rubric, setRubric] = useState<LearnsetRubric | null>(null);
  // The line strip's diff baseline: the anchor's profile frozen at workbench OPEN
  // (ac12). Captured once; the live entry is diffed against it as facets lock.
  const [before] = useState(() => snapshotProfile(entry));
  // The active stage's sub-surface label for the overhead rail (e.g. "create new"
  // when the abilities CREATE NEW panel is open); null otherwise (ac11).
  const [subSurface, setSubSurface] = useState<string | null>(null);
  // Custom content created mid-flow (name + kind). Auto-persisted on CONFIRM by its
  // panel; recorded here so a note is appended to the direction sent to SUBSEQUENT
  // suggest calls — the model is actively steered to use it, not merely allowed to
  // (the ordering guard: pool-level awareness already exists; this is the nudge).
  const [createdContent, setCreatedContent] = useState<{ name: string; kind: "ability" | "move" }[]>(
    [],
  );

  const redirectRef = useRef<HTMLTextAreaElement>(null);
  const actionsRef = useRef<StageActions | null>(null);

  const byId = useMemo(() => new Map(allEntries.map((e) => [e.chrooked_id, e])), [allEntries]);
  const linePre = useMemo(() => preEvos(entry, byId), [entry, byId]);
  const movePower = useMemo(() => {
    const map = new Map<string, number | null>();
    for (const move of moves) map.set(move.name, move.power);
    return map;
  }, [moves]);
  // Move name (lowercased) → type + category, so the learnset stage tints/bolds/
  // italicizes rows exactly like the profile learnset.
  const moveMeta = useMemo(() => {
    const map = new Map<string, { type: string; category: string }>();
    for (const move of moves) map.set(move.name.toLowerCase(), { type: move.type, category: move.category });
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
    // Dedupe an identical consecutive steer (e.g. a retry after a propose error)
    // so the design log doesn't repeat itself.
    setCorrections((prev) =>
      prev[prev.length - 1] === text ? prev : [...prev, text],
    );
  }, []);

  // A mid-flow create persisted to the Ruleset; record it + refresh the dex so the
  // new move/ability shows in the option pools and later suggests can reference it.
  const handleCreated = useCallback(
    (name: string, kind: "ability" | "move") => {
      setCreatedContent((prev) => [...prev, { name, kind }]);
      onSaved();
    },
    [onSaved],
  );

  // The direction sent to subsequent design-stage suggests: the human's steer plus
  // a per-item nudge to prefer any custom content created this session for this mon.
  const injectedDirection = useMemo(() => {
    if (createdContent.length === 0) return direction;
    const notes = createdContent
      .map(
        (c) =>
          ` Note: the custom ${c.kind} '${c.name}' was created specifically for ${entry.name} — prefer to use it.`,
      )
      .join("");
    return `${direction}${notes}`;
  }, [direction, createdContent, entry.name]);

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
    if (paused) return;
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
        onPark();
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
  }, [paused, onPark]);

  const commonProps: CommonStageProps = {
    entry,
    initialDirection: injectedDirection,
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
          // KEPT facets constrain the lore options: a facet not in `selected` is
          // KEEP, so its current value is fixed and the options must honor it.
          keptTypes={selected.has("typing") ? undefined : entry.types}
          keptAbilities={selected.has("abilities") ? undefined : entry.abilities}
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
      panel = (
        <AbilitiesStage
          {...commonProps}
          abilityOptions={abilityOptions}
          byId={byId}
          onSubSurface={setSubSurface}
          onSaved={onSaved}
          onCreated={handleCreated}
        />
      );
      break;
    case "learnset":
      panel = (
        <LearnsetStage
          {...commonProps}
          moveOptions={moveOptions}
          movePower={movePower}
          moveMeta={moveMeta}
          speciesTypes={entry.types}
          attackCategory={attackCategory(entry.stats)}
          rubric={rubric}
          onSubSurface={setSubSurface}
          onCreated={handleCreated}
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
          direction={direction.trim() || facetSummary(selected)}
          corrections={corrections}
          onStage={(sub) => onStage(sub)}
          onDone={onExit}
        />
      );
  }

  return (
    <div className="mk-workbench" id="makeover-workbench">
      <header className="mk-workbench__head">
        <button type="button" className="mk-workbench__exit mono" onClick={onPark} aria-label="Back to the dex — the makeover stays open (Esc)">
          ← dex
        </button>
        <h2 className="mk-workbench__title">
          makeover · <strong>{entry.name}</strong>
        </h2>
      </header>
      <OverheadRail
        selected={selected}
        sessionLocked={sessionLocked}
        active={active}
        subLabel={subSurface}
      />
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
          before={before}
          facts={facts}
          lockedLearnset={sessionLocked.has("learnset") || sessionLocked.has("mirror")}
          backdropTargetId={backdropTargetId}
        />
      </div>
    </div>
  );
}
