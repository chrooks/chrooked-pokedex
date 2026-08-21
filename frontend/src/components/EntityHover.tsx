/* Hover cards for entity names: wrap an inline ability or move name and a
   compact read-only card appears on hover / keyboard focus — the ability's
   description, or the move's vitals (type, category, power, accuracy, PP,
   priority, target) mirroring the MoveDetail field order. Unknown names render
   the children untouched, so callers never guard. Portal-mounted so the card
   escapes the ledger's scroll clipping. */

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { useAbilityInfo, useMoveInfo } from "../lib/entityInfo";
import { placeCard } from "../lib/hoverPlacement";
import { targetLabel } from "../lib/moveTargets";
import { TypeChip } from "./TypeChip";
import { CategoryChip } from "./CategoryChip";
import { TargetGlyph } from "./TargetGrid";
import "./entity-hover.css";

const OPEN_DELAY_MS = 350;

type HoverShellProps = {
  /** The card body; null → no card, children render bare. */
  card: ReactNode | null;
  children: ReactNode;
};

/** The shared open/close + placement machinery. The anchor is a plain inline
    span so the wrapped link/button keeps its own semantics and focus ring. */
function HoverShell({ card, children }: HoverShellProps) {
  const tipId = useId();
  const anchorRef = useRef<HTMLSpanElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<number | null>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  const cancel = useCallback(() => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const show = useCallback(
    (delay: number) => {
      cancel();
      timerRef.current = window.setTimeout(() => setOpen(true), delay);
    },
    [cancel],
  );

  const hide = useCallback(() => {
    cancel();
    setOpen(false);
    setPos(null);
  }, [cancel]);

  useEffect(() => cancel, [cancel]);

  // Measure after the card mounts, then place it — the card renders invisibly
  // for one frame (opacity handles it) so its real size drives the clamp.
  useLayoutEffect(() => {
    if (!open) return;
    const anchor = anchorRef.current?.getBoundingClientRect();
    const size = cardRef.current?.getBoundingClientRect();
    if (!anchor || !size) return;
    setPos(
      placeCard(
        { top: anchor.top, bottom: anchor.bottom, left: anchor.left },
        { width: size.width, height: size.height },
        { width: window.innerWidth, height: window.innerHeight },
      ),
    );
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") hide();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, hide]);

  if (card === null) return <>{children}</>;

  return (
    <span
      ref={anchorRef}
      className="ehover__anchor"
      aria-describedby={open ? tipId : undefined}
      onMouseEnter={() => show(OPEN_DELAY_MS)}
      onMouseLeave={hide}
      onFocus={() => show(0)}
      onBlur={hide}
    >
      {children}
      {open &&
        createPortal(
          <div
            ref={cardRef}
            id={tipId}
            role="tooltip"
            className="ehover__card"
            data-placed={pos !== null}
            style={pos ? { top: pos.top, left: pos.left } : undefined}
          >
            {card}
          </div>,
          document.body,
        )}
    </span>
  );
}

/** Hover card for an ability name: the ability's description. */
export function AbilityHover({ name, children }: { name: string | null; children: ReactNode }) {
  const ability = useAbilityInfo(name);
  const card = ability ? (
    <>
      <p className="ehover__title">{ability.name}</p>
      <p className="ehover__desc">{ability.description || "No description."}</p>
    </>
  ) : null;
  return <HoverShell card={card}>{children}</HoverShell>;
}

/** Hover card for a move name: the move's vitals, MoveDetail's field order. */
export function MoveHover({ name, children }: { name: string | null; children: ReactNode }) {
  const move = useMoveInfo(name);
  const card = move ? (
    <>
      <p className="ehover__title">{move.name}</p>
      <div className="ehover__chips">
        <TypeChip type={move.type} variant="code" />
        <CategoryChip category={move.category} variant="full" />
      </div>
      <dl className="ehover__stats mono">
        <dt>Power</dt>
        <dd>{move.power ?? "—"}</dd>
        <dt>Accuracy</dt>
        <dd>{move.accuracy ?? "—"}</dd>
        <dt>PP</dt>
        <dd>{move.pp ?? "—"}</dd>
        <dt>Priority</dt>
        <dd>{move.priority}</dd>
      </dl>
      {move.target && (
        <p className="ehover__target">
          <TargetGlyph target={move.target} />
          {targetLabel(move.target)}
        </p>
      )}
      {move.description && <p className="ehover__desc">{move.description}</p>}
    </>
  ) : null;
  return <HoverShell card={card}>{children}</HoverShell>;
}
