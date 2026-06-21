/* The contract a section renderer must satisfy so the generic
   {@link ProposedColumn} shell can drive it without any section-specific logic
   (ac7). The shell owns the flow (affordance → input → loader → rationale →
   alternatives → Apply); a renderer owns only the cell layout, the per-cell
   edit affordances, and the draft→Override mapping for its section. */

import type { ReactNode } from "react";
import type { DexEntry, ProposalAlternative, SpeciesOverride } from "../../types";

export interface CellRenderArgs<Draft> {
  /** The species being edited (the source of the current values). */
  entry: DexEntry;
  /** The current working draft (null before a proposal). */
  draft: Draft | null;
  /** The model's per-key rationale (slot name, or "learnset"). */
  rationale: Record<string, string>;
  /** Curate: hand back a new draft after a cell edit or an alternative swap. */
  onEdit: (draft: Draft) => void;
  /** True once Apply has written; the renderer keys solid (not provisional). */
  applied: boolean;
}

/** A section renderer: the cell grid plus the merge mapping. Generic over its
    `Draft` shape (abilities vs learnset). */
export interface SectionRenderer<Draft> {
  /** Stable id stem + section title for the shell's header and labels. */
  id: string;
  title: string;
  /** The accessible label for the `✦ suggest` affordance. Per-section so the
      article reads cleanly ("Suggest abilities…" plural vs "Suggest a learnset…"
      singular) instead of a generated "a abilities". */
  suggestLabel: string;
  /** The placeholder for the freeform direction input. */
  placeholder: string;
  /** Render the current │ proposed cell grid for this section. */
  renderCells: (args: CellRenderArgs<Draft>) => ReactNode;
  /** Swap an alternative into the draft, returning the next draft. */
  applyAlternative: (draft: Draft | null, alt: ProposalAlternative) => Draft;
  /** Merge the curated draft into the raw Override (read-merge-write). Only this
      section's field is touched; every other field is carried through untouched
      so a partial Override survives Apply (mirrors SpeciesEditor). */
  mergeDraft: (raw: SpeciesOverride, draft: Draft) => SpeciesOverride;
}
