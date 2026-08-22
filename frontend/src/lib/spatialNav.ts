/** Move DOM focus in a compass direction, by geometry.
 *
 * The dex grid is a plain list of <button> cells with no cursor state of its
 * own, so rather than teaching every view to track a cursor, the D-pad just
 * drives real focus. That means one implementation serves the grid, the table,
 * the icon rail and the detail panel, and everything keeps its existing
 * focus-visible styling and click handlers for free.
 *
 * "Nearest in that direction" beats DOM order: in a 4-column grid, Down has to
 * land one row below, and DOM order would walk one cell sideways instead.
 */

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export type Direction = "up" | "down" | "left" | "right";

/** Visible, on-screen, focusable elements — the candidates worth moving to. */
function candidates(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => {
    if (el.closest("[inert]") || el.hidden) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return false;
    // Off-screen rows of a virtualized list are real elements; skip them or the
    // cursor teleports to something the user cannot see.
    return rect.bottom > 0 && rect.right > 0 &&
      rect.top < window.innerHeight && rect.left < window.innerWidth;
  });
}

/** Just enough of a DOMRect to score against — keeps the geometry testable
    without a DOM, which is how every other test in this project is written. */
export type Box = { left: number; top: number; width: number; height: number };

function centre(box: Box) {
  return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
}

function toBox(el: Element): Box {
  const r = el.getBoundingClientRect();
  return { left: r.left, top: r.top, width: r.width, height: r.height };
}

/** Drift across the travel axis is penalised 3x. Without it, pressing Down in a
    grid frequently lands on a diagonal neighbour that happens to be a few
    pixels closer than the cell directly below. */
const ACROSS_AXIS_PENALTY = 3;

/**
 * Index of the best candidate in `direction`, or null when nothing lies that
 * way. Pure geometry — `focusInDirection` is the DOM wrapper around it.
 */
export function pickInDirection(
  from: Box,
  candidates: readonly Box[],
  direction: Direction,
): number | null {
  const origin = centre(from);
  const horizontal = direction === "left" || direction === "right";
  const sign = direction === "up" || direction === "left" ? -1 : 1;

  let best: number | null = null;
  let bestScore = Infinity;

  candidates.forEach((box, index) => {
    const to = centre(box);
    const along = horizontal ? (to.x - origin.x) * sign : (to.y - origin.y) * sign;
    const across = horizontal ? Math.abs(to.y - origin.y) : Math.abs(to.x - origin.x);
    // Must actually lie in the pressed direction, by more than a rounding wobble.
    if (along <= 1) return;
    const score = along + across * ACROSS_AXIS_PENALTY;
    if (score < bestScore) {
      bestScore = score;
      best = index;
    }
  });

  return best;
}

/**
 * Focus the nearest focusable element in `direction`. Returns false when there
 * is nothing that way, so the caller can decide whether to scroll instead.
 */
export function focusInDirection(direction: Direction): boolean {
  const active = document.activeElement as HTMLElement | null;
  const pool = candidates();
  if (pool.length === 0) return false;

  // Nothing focused yet (or focus is on <body>): start at the first candidate.
  if (!active || active === document.body || !pool.includes(active)) {
    pool[0].focus();
    return true;
  }

  const others = pool.filter((el) => el !== active);
  const index = pickInDirection(toBox(active), others.map(toBox), direction);
  if (index === null) return false;

  const target = others[index];
  target.focus();
  target.scrollIntoView({ block: "nearest", inline: "nearest" });
  return true;
}

/** Click whatever is focused — the A button's job. */
export function activateFocused(): boolean {
  const active = document.activeElement as HTMLElement | null;
  if (!active || active === document.body) return false;
  active.click();
  return true;
}
