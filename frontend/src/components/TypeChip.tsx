import { typeSlug } from "../lib/format";
import "./type-chip.css";

type Props = {
  type: string;
  /** "code" renders the dense 3-letter grid token; "full" renders the name. */
  variant?: "code" | "full";
};

/**
 * One Pokémon type, in its franchise color. The chip pulls a bright label and a
 * dark tint from a single `--type-*` token via color-mix, so every type stays
 * AA-legible on the dark surface (see DESIGN.md). The label is also real text,
 * so type identity never depends on color alone.
 */
export function TypeChip({ type, variant = "full" }: Props) {
  const slug = typeSlug(type);
  const style = { "--chip": `var(--type-${slug}, var(--text-dim))` } as React.CSSProperties;
  return (
    <span className={`type-chip type-chip--${variant}`} style={style} data-type={slug}>
      {variant === "code" ? type.slice(0, 3).toUpperCase() : type}
    </span>
  );
}
