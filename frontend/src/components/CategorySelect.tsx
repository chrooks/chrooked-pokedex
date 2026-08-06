import { CATEGORIES, CategoryGlyph, categoryLabel, type Category } from "./CategoryChip";
import "./category-select.css";

type Props = {
  id: string;
  value: string;
  onChange: (value: Category) => void;
  /** Accessible name for the group. */
  label: string;
};

/**
 * The damage-category picker. A native <select> is text-only, so it cannot show
 * the category glyph — and a category that reads as a shape in the moves table
 * but as bare lowercase text in the editor is the same data wearing two faces.
 * Three options is few enough that a radio group beats a listbox: every choice
 * is visible, and Arrow keys move between them for free.
 */
export function CategorySelect({ id, value, onChange, label }: Props) {
  return (
    <div className="cat-select" id={id} role="radiogroup" aria-label={label}>
      {CATEGORIES.map((category) => (
        <button
          key={category}
          type="button"
          role="radio"
          id={`${id}-${category}`}
          className="cat-select__opt"
          data-category={category}
          aria-checked={value === category}
          onClick={() => onChange(category)}
        >
          <CategoryGlyph category={category} />
          {categoryLabel(category)}
        </button>
      ))}
    </div>
  );
}
