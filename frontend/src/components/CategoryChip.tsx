import "./category-chip.css";

export type Category = "physical" | "special" | "status";

type Props = {
  category: Category;
  /** "icon" renders the dense glyph-only badge; "full" adds the label text. */
  variant?: "icon" | "full";
};

/**
 * A move's damage category, rendered as the franchise's physical/special/status
 * split: a color-coded glyph so the category reads at a glance while scanning,
 * never as gray text three columns deep. Each category owns a hue plus a
 * distinct shape, so identity never depends on color alone (see DESIGN.md).
 */
export function CategoryChip({ category, variant = "full" }: Props) {
  const meta = CATEGORY_META[category];
  return (
    <span
      className={`cat-chip cat-chip--${variant}`}
      data-category={category}
      title={meta.label}
    >
      <Glyph category={category} />
      {variant === "full" && <span className="cat-chip__label">{meta.label}</span>}
    </span>
  );
}

const CATEGORY_META: Record<Category, { label: string }> = {
  physical: { label: "Physical" },
  special: { label: "Special" },
  status: { label: "Status" },
};

export const CATEGORIES: readonly Category[] = ["physical", "special", "status"];

/** The display label for a category, so no caller re-capitalizes by hand. */
export function categoryLabel(category: Category): string {
  return CATEGORY_META[category].label;
}

/**
 * The bare glyph, for hosts that carry their own shell (a segmented button, an
 * editor trigger). Every surface that shows a damage category renders THIS —
 * the chip, the picker, and the distributor's split buttons all share one shape
 * set, so physical never means one thing here and another thing there.
 */
export function CategoryGlyph({ category }: { category: Category }) {
  return <Glyph category={category} />;
}

/** Three shapes that read apart even in grayscale: a fist-impact burst, a
    radiating special starburst, and a quiet status ring. */
function Glyph({ category }: { category: Category }) {
  if (category === "physical") {
    return (
      <svg className="cat-chip__glyph" viewBox="0 0 12 12" aria-hidden="true">
        <path
          d="M6 0.5 7.2 4 11 4 8 6.3 9 10 6 7.8 3 10 4 6.3 1 4 4.8 4Z"
          fill="currentColor"
        />
      </svg>
    );
  }
  if (category === "special") {
    return (
      <svg className="cat-chip__glyph" viewBox="0 0 12 12" aria-hidden="true">
        <circle cx="6" cy="6" r="2.2" fill="currentColor" />
        <circle cx="6" cy="6" r="4.4" fill="none" stroke="currentColor" strokeWidth="1.1" strokeDasharray="2.2 1.6" />
      </svg>
    );
  }
  return (
    <svg className="cat-chip__glyph" viewBox="0 0 12 12" aria-hidden="true">
      <circle cx="6" cy="6" r="4" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="6" cy="6" r="1.3" fill="currentColor" />
    </svg>
  );
}
