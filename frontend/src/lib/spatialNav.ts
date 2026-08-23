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

/**
 * How far past the viewport edge a candidate may sit and still be reachable.
 *
 * Zero margin meant the cursor stopped dead at the last visible row: the next
 * row exists in the DOM just below the fold, but was filtered out, so the press
 * did nothing and the list had to be scrolled by hand. A margin of roughly one
 * row lets the cursor step over the edge and drag the view with it, while still
 * excluding the far-off rows a virtualized list keeps mounted — landing on one
 * of those would teleport the cursor somewhere invisible.
 */
const OFFSCREEN_REACH_PX = 120;

/** Focusable elements at or near the viewport — the candidates worth moving to. */
function candidates(): HTMLElement[] {
  const reach = OFFSCREEN_REACH_PX;
  return [...document.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => {
    if (el.closest("[inert]") || el.hidden) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return false;
    return rect.bottom > -reach && rect.right > -reach &&
      rect.top < window.innerHeight + reach && rect.left < window.innerWidth + reach;
  });
}

/** The nearest ancestor that actually scrolls, or null. */
function scrollHostFor(el: Element | null): HTMLElement | null {
  let node = el?.parentElement ?? null;
  while (node) {
    const style = getComputedStyle(node);
    const scrollsY = /(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 2;
    const scrollsX = /(auto|scroll)/.test(style.overflowX) && node.scrollWidth > node.clientWidth + 2;
    if (scrollsY || scrollsX) return node;
    node = node.parentElement;
  }
  return null;
}

/**
 * Nudge the surrounding scroller when the cursor has run out of candidates.
 *
 * A long list is virtualized: the rows past the fold do not exist yet, so there
 * is nothing to focus until the view moves. Scrolling first and retrying on the
 * next frame gives those rows a chance to mount, which makes one press feel
 * like one step rather than requiring the user to scroll by hand first.
 */
function scrollAndRetry(direction: Direction, from: Element | null): boolean {
  const host = scrollHostFor(from) ?? document.scrollingElement;
  if (!(host instanceof HTMLElement)) return false;

  const vertical = direction === "up" || direction === "down";
  const sign = direction === "up" || direction === "left" ? -1 : 1;
  const step = Math.max(80, Math.round((vertical ? host.clientHeight : host.clientWidth) * 0.4));

  const before = vertical ? host.scrollTop : host.scrollLeft;
  if (vertical) host.scrollTop = before + step * sign;
  else host.scrollLeft = before + step * sign;
  const moved = (vertical ? host.scrollTop : host.scrollLeft) !== before;
  if (!moved) return false; // genuinely at the end of the list

  // Let the newly-revealed rows mount before looking for something to focus.
  requestAnimationFrame(() => focusInDirection(direction));
  return true;
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
    markPadFocus(pool[0]);
    return true;
  }

  const others = pool.filter((el) => el !== active);
  const index = pickInDirection(toBox(active), others.map(toBox), direction);
  // Nothing that way yet — the list may simply not have rendered it. Move the
  // view and try again rather than stopping and making the user scroll by hand.
  if (index === null) return scrollAndRetry(direction, active);

  const target = others[index];
  target.focus();
  markPadFocus(target);
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

/**
 * The attribute that marks the controller's cursor.
 *
 * `:focus-visible` is not enough. The browser decides whether to draw it from
 * how focus was last moved, and a programmatic `.focus()` call driven by a
 * gamepad is not recognised as a keyboard interaction — so the D-pad moved
 * focus with nothing drawn on screen, and there was no way to tell what the A
 * button was about to activate. An explicit attribute takes that decision away
 * from the heuristic.
 */
const PAD_FOCUS_ATTR = "data-padfocus";

/** Stamp the controller cursor onto `el`, clearing it from wherever it was. */
export function markPadFocus(el: Element | null): void {
  const previous = document.querySelector(`[${PAD_FOCUS_ATTR}]`);
  if (previous && previous !== el) previous.removeAttribute(PAD_FOCUS_ATTR);
  if (el) el.setAttribute(PAD_FOCUS_ATTR, "true");
}

/** Drop the controller cursor — used when a real pointer takes over, so the
    ring does not linger somewhere the user is no longer looking. */
export function clearPadFocus(): void {
  document.querySelector(`[${PAD_FOCUS_ATTR}]`)?.removeAttribute(PAD_FOCUS_ATTR);
}
