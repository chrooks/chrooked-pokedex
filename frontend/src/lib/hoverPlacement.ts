/* Pure placement math for the hover card: prefer below the anchor, flip above
   when the viewport runs out, clamp horizontally. Kept DOM-free so it tests. */

export interface Rect {
  top: number;
  bottom: number;
  left: number;
}

export interface Size {
  width: number;
  height: number;
}

const GAP = 6;
const MARGIN = 8;

export function placeCard(
  anchor: Rect,
  card: Size,
  viewport: Size,
): { top: number; left: number } {
  const below = anchor.bottom + GAP;
  const fitsBelow = below + card.height + MARGIN <= viewport.height;
  const top = fitsBelow ? below : Math.max(MARGIN, anchor.top - GAP - card.height);
  const left = Math.min(
    Math.max(MARGIN, anchor.left),
    Math.max(MARGIN, viewport.width - card.width - MARGIN),
  );
  return { top, left };
}
