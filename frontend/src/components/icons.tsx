/* The nav icon set.
 *
 * Authored on ONE 16x16 grid with solid `currentColor` fills, matching the
 * house style already set by CategoryChip's glyphs — solid geometry reads at
 * 16px on a handheld screen where a 1px outline stroke would disappear, and it
 * suits the segmented-readout device flavor better than a hairline outline set.
 *
 * These exist because the compact rail drops its text labels: at that point the
 * glyph IS the label, so each one has to be distinguishable at a glance rather
 * than decorative. Shapes are chosen to differ in silhouette, not just detail —
 * a grid, a chevron pair, a burst, a matrix, a ring, a chip.
 */

type IconProps = { className?: string };

const BASE = {
  viewBox: "0 0 16 16",
  fill: "currentColor",
  "aria-hidden": true as const,
  focusable: "false" as const,
};

/** Species — the dex grid itself: four cells. */
export function IconSpecies({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <rect x="2" y="2" width="5" height="5" rx="1" />
      <rect x="9" y="2" width="5" height="5" rx="1" />
      <rect x="2" y="9" width="5" height="5" rx="1" />
      <rect x="9" y="9" width="5" height="5" rx="1" />
    </svg>
  );
}

/** Moves — a chevron pair: the forward motion of an attack. */
export function IconMoves({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <path d="M2.6 2.9 4.3 1.5 9.2 8l-4.9 6.5-1.7-1.4L6.4 8Z" />
      <path d="M8.4 2.9 10.1 1.5 15 8l-4.9 6.5-1.7-1.4L12.2 8Z" />
    </svg>
  );
}

/** Abilities — a four-point burst: innate power, not a move. */
export function IconAbilities({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <path d="M8 0.5 9.9 6.1 15.5 8 9.9 9.9 8 15.5 6.1 9.9 0.5 8 6.1 6.1Z" />
    </svg>
  );
}

/** Type Chart — a shield: what a type resists and what gets through it.
    Deliberately NOT another matrix of cells — at 16px a 3x3 grid was
    indistinguishable from the Species dex-grid glyph, which is the one
    confusion an icon-only rail cannot afford. */
export function IconTypeChart({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <path d="M8 0.7 14.4 3.1v4.6c0 3.8-2.7 6.1-6.4 7.6-3.7-1.5-6.4-3.8-6.4-7.6V3.1Zm0 2.15L3.6 4.5v3.2c0 2.6 1.6 4.3 4.4 5.5 2.8-1.2 4.4-2.9 4.4-5.5V4.5Z" />
      <path d="M8 5.2 9.1 7.5l2.3.3-1.7 1.6.4 2.3L8 10.6l-2.1 1.1.4-2.3-1.7-1.6 2.3-.3Z" />
    </svg>
  );
}

/** Statuses — the quiet ring, borrowed from the status damage-category glyph
    so "status" reads the same everywhere it appears. */
export function IconStatuses({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1Zm0 2a5 5 0 1 1 0 10A5 5 0 0 1 8 3Z" />
      <circle cx="8" cy="8" r="2.2" />
    </svg>
  );
}

/** Behaviors — an integrated-circuit chip: mechanics that need engine code.
    Four legs per side would turn to mud at 16px; two reads as a chip. */
export function IconBehaviors({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <rect x="3.8" y="3.8" width="8.4" height="8.4" rx="1.2" />
      <path d="M5.9 0.8h1.5v2.4H5.9zM8.6 0.8h1.5v2.4H8.6zM5.9 12.8h1.5v2.4H5.9zM8.6 12.8h1.5v2.4H8.6zM0.8 5.9h2.4v1.5H0.8zM0.8 8.6h2.4v1.5H0.8zM12.8 5.9h2.4v1.5h-2.4zM12.8 8.6h2.4v1.5h-2.4Z" />
    </svg>
  );
}

/** Team — a party of six. */
export function IconTeam({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <circle cx="4" cy="4" r="2" />
      <circle cx="8" cy="4" r="2" />
      <circle cx="12" cy="4" r="2" />
      <circle cx="4" cy="11" r="2" />
      <circle cx="8" cy="11" r="2" />
      <circle cx="12" cy="11" r="2" />
    </svg>
  );
}

/** Ledger — the change record: stacked entries, the top one current. */
export function IconLedger({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <rect x="1.5" y="3" width="13" height="2" rx="0.8" />
      <rect x="1.5" y="7" width="9.5" height="2" rx="0.8" />
      <rect x="1.5" y="11" width="11.5" height="2" rx="0.8" />
    </svg>
  );
}

/** Search. */
export function IconSearch({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <path d="M7 1.5a5.5 5.5 0 1 0 3.36 9.85l3.14 3.15 1.35-1.35-3.15-3.14A5.5 5.5 0 0 0 7 1.5Zm0 2a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z" />
    </svg>
  );
}

/** Filters — the sliders already used by the targets control. */
export function IconFilters({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <rect x="1" y="3" width="14" height="1.6" rx="0.8" />
      <rect x="1" y="7.2" width="14" height="1.6" rx="0.8" />
      <rect x="1" y="11.4" width="14" height="1.6" rx="0.8" />
      <circle cx="5" cy="3.8" r="2.2" />
      <circle cx="11" cy="8" r="2.2" />
      <circle cx="7" cy="12.2" r="2.2" />
    </svg>
  );
}

/** Table view — a header row over data rows. Distinct from IconLedger's
    ragged stack of bars, which means "the change record", not "rows". */
export function IconTable({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <path d="M1.5 2h13v3.2h-13z" />
      <path d="M1.5 6.6h13v1.9h-13zM1.5 9.6h13v1.9h-13zM1.5 12.6h13V14h-13z" />
    </svg>
  );
}

/** Grid view — the sprite-led cell layout. */
export function IconGridView({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <rect x="1.5" y="1.5" width="5.6" height="5.6" rx="1" />
      <rect x="8.9" y="1.5" width="5.6" height="5.6" rx="1" />
      <rect x="1.5" y="8.9" width="5.6" height="5.6" rx="1" />
      <rect x="8.9" y="8.9" width="5.6" height="5.6" rx="1" />
    </svg>
  );
}

/** Close. */
export function IconClose({ className }: IconProps) {
  return (
    <svg {...BASE} className={className}>
      <path d="M3.4 2 8 6.6 12.6 2 14 3.4 9.4 8l4.6 4.6-1.4 1.4L8 9.4 3.4 14 2 12.6 6.6 8 2 3.4Z" />
    </svg>
  );
}
