/* The hybrid tweak loop's re-roll rule, as pure functions: when the author edits
   a proposal row and then re-rolls (the redirect box), their edits ride along as
   CONSTRAINTS appended to the direction — so a re-roll refines rather than
   discards their hand-tuning (ac3). Section-specific diff against the last
   proposed baseline; unit-tested without a DOM. */

import type {
  AbilityDraft,
  LearnsetDraft,
  LearnsetMove,
  LearnsetDraftMove,
} from "../types";

export type MakeoverSection = "typing" | "stats" | "abilities" | "learnset";

export interface TypingDraft {
  types: string[];
}
export interface StatsDraft {
  stats: Record<string, number>;
}

/** The union of the four section draft shapes the workbench edits. */
export type SectionDraft = TypingDraft | StatsDraft | AbilityDraft | LearnsetDraft;

const STAT_KEYS = ["hp", "atk", "def", "spa", "spd", "spe"] as const;
const ABILITY_SLOTS = ["primary", "secondary", "hidden"] as const;
// Cap so a heavily hand-edited learnset does not balloon the re-roll prompt.
const MAX_CONSTRAINTS = 10;

function learnsetKeys(rows: readonly (LearnsetMove | LearnsetDraftMove)[]): Set<string> {
  return new Set(rows.map((r) => `${r.level}::${r.move.trim().toLowerCase()}`));
}

/** Derive human-readable constraint lines from the author's edits (the current
    `edited` draft vs the `baseline` the model last proposed). Empty when nothing
    was hand-changed. */
export function deriveConstraints(
  section: MakeoverSection,
  baseline: SectionDraft | null,
  edited: SectionDraft | null,
): string[] {
  if (edited === null) return [];
  if (section === "typing") {
    const base = (baseline as TypingDraft | null)?.types ?? [];
    const now = (edited as TypingDraft).types;
    if (now.join("/") !== base.join("/") && now.length > 0) {
      return [`the typing ${now.join("/")}`];
    }
    return [];
  }
  if (section === "stats") {
    const base = (baseline as StatsDraft | null)?.stats ?? {};
    const now = (edited as StatsDraft).stats;
    const out: string[] = [];
    for (const key of STAT_KEYS) {
      if (now[key] !== undefined && now[key] !== base[key]) {
        out.push(`${key.toUpperCase()} at ${now[key]}`);
      }
    }
    return out;
  }
  if (section === "abilities") {
    const base = (baseline as AbilityDraft | null)?.abilities ?? {};
    const now = (edited as AbilityDraft).abilities;
    const out: string[] = [];
    for (const slot of ABILITY_SLOTS) {
      const value = now[slot];
      if (value && value !== base[slot]) {
        out.push(`the ${slot} ability ${value}`);
      }
    }
    return out;
  }
  // learnset — added rows the author placed and rows they removed become "keep"
  // and "do not include" constraints.
  const baseRows = (baseline as LearnsetDraft | null)?.learnset ?? [];
  const nowRows = (edited as LearnsetDraft).learnset;
  const baseKeys = learnsetKeys(baseRows);
  const nowByMove = new Set(nowRows.map((r) => r.move.trim().toLowerCase()));
  const out: string[] = [];
  for (const row of nowRows) {
    if (!baseKeys.has(`${row.level}::${row.move.trim().toLowerCase()}`)) {
      out.push(
        row.level === 0
          ? `${row.move} at L0 (on evolution)`
          : `${row.move} at L${row.level}`,
      );
    }
  }
  for (const row of baseRows) {
    if (!nowByMove.has(row.move.trim().toLowerCase())) {
      out.push(`do not include ${row.move}`);
    }
  }
  return out.slice(0, MAX_CONSTRAINTS);
}

/** Fold the derived constraints into the re-roll direction. The base direction
    stays first; the constraints follow as an explicit "keep fixed" block so the
    model's next proposal honors the author's hand-edits. */
export function composeDirection(base: string, constraints: readonly string[]): string {
  const trimmed = base.trim();
  if (constraints.length === 0) return trimmed;
  const block =
    "Keep these author edits fixed on the re-roll:\n" +
    constraints.map((c) => `- ${c}`).join("\n");
  return trimmed ? `${trimmed}\n\n${block}` : block;
}

/** Convenience: the full re-roll direction given the base steer plus the diff
    between the last baseline and the current (edited) draft. */
export function rerollDirection(
  section: MakeoverSection,
  base: string,
  baseline: SectionDraft | null,
  edited: SectionDraft | null,
): string {
  return composeDirection(base, deriveConstraints(section, baseline, edited));
}
