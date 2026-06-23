/* JSON shapes returned by the FastAPI layer. Mirror the Python serializers in
   web/dex.py and web/collections.py. */

export type OverridableField =
  | "types"
  | "abilities"
  | "stats"
  | "learnset"
  | "evolution";

export interface AbilitySlots {
  primary: string | null;
  secondary: string | null;
  hidden: string | null;
}

export interface LearnsetMove {
  level: number;
  move: string;
}

/** One forward evolution edge: this species evolves INTO `to` by `method`.
    `to` is the target's chrooked_id (the dex navigation key); `to_name` is its
    display name. Base-derived; a species can have several (branching evolvers
    like Eevee). */
export interface EvolvesInto {
  to: string;
  to_name: string;
  /** Target national dex number — lets the cross-link resolve a sprite for base
      species (the sprite-id form map keys only forms). Null for a numberless form. */
  to_dex: number | null;
  method: string;
}

/** A species' pre-evolution (the backward edge). Base-derived `evolution` carries
    `from` as a chrooked_id, a `from_name` display name, and a readable string
    `method` ("Level 26"). A Ruleset *override* sets only `from` + a structured
    `method` dict (no `from_name`); the section renders either shape. */
export interface Evolution {
  from: string | null;
  from_name?: string;
  /** Pre-evo national dex number (base-derived), for the cross-link sprite. */
  from_dex?: number | null;
  method: string | Record<string, unknown>;
  /** Structured form of a backdrop display-string `method` ("Level 36"). The API
      ships this alongside the string: `kind` is "Level"/"Item"/… (or the raw
      pokeemerald token like "EVO_LEVEL"), `param` the value ("36"). Absent on the
      Override shape, where `method` is already a structured dict. */
  method_detail?: { kind: string; param: string };
}

/** Pre-override values for whatever the Ruleset changed (base → now diff). */
export interface DexBaseValues {
  types?: string[];
  abilities?: AbilitySlots;
  stats?: Record<string, number>;
  learnset?: LearnsetMove[];
}

export interface DexEntry {
  dex: number | null;
  chrooked_id: string;
  name: string;
  types: string[];
  abilities: AbilitySlots;
  stats: Record<string, number>;
  learnset: LearnsetMove[];
  evolution: Evolution | null;
  /** Forward evolution edges (base-derived). Empty for a final form. */
  evolves_into: EvolvesInto[];
  /** True when the species has no outgoing evolution (a final form or a
      single-stage mon). A base fact from the snapshot; drives the Fully Evolved
      class. */
  fully_evolved: boolean;
  overridden_fields: OverridableField[];
  base: DexBaseValues;
  /** Fields scoped to the active backdrop Target (present only on a backdrop dex
      that has a bound Override namespace). Drives the per-field "this target only"
      badge. Absent on the Canon dex and on targets with no namespace. */
  target_overridden_fields?: OverridableField[];
}

/** The raw Ruleset Override for one species (overrides-only), as returned by
    `GET /api/species/{id}` and sent back on save. Distinct from {@link DexEntry},
    which is the merged base ⊕ Override view. A null field is "not overridden". */
export interface SpeciesOverride {
  name: string;
  chrooked_id: string;
  aka: Record<string, unknown>;
  types: string[] | null;
  abilities: AbilitySlots | null;
  stats: Record<string, number> | null;
  learnset: LearnsetMove[] | null;
  evolution: Evolution | null;
}

/** One alternative the model offered alongside the primary draft (#6/#7). The
    `value` shape is section-specific — an ability name for an ability slot, a
    `(level, move)` pair for a learnset — so it is left untyped at this layer and
    narrowed by each section's renderer. */
export interface ProposalAlternative {
  value: unknown;
  rationale: string;
}

/** The shared envelope every `/suggest/*` endpoint returns: a `draft` (the
    proposed values), per-key `rationale`, and a list of swappable
    `alternatives`. `Draft` and the `rationale` keys are section-specific. */
export interface SuggestResponse<Draft> {
  draft: Draft;
  rationale: Record<string, string>;
  alternatives: ProposalAlternative[];
}

/** `POST /api/species/{id}/suggest/ability` — a proposed abilities block. Each
    slot is optional; an absent slot means "keep the current value". */
export interface AbilityDraft {
  abilities: {
    primary?: string;
    secondary?: string;
    hidden?: string;
  };
}

export type AbilityProposal = SuggestResponse<AbilityDraft>;

/** One proposed learnset row, carrying the model's per-row `reasoning`. */
export interface LearnsetDraftMove {
  level: number;
  move: string;
  reasoning?: string;
}

/** `POST /api/species/{id}/suggest/learnset` — a whole proposed learnset. */
export interface LearnsetDraft {
  learnset: LearnsetDraftMove[];
}

export type LearnsetProposal = SuggestResponse<LearnsetDraft>;

export interface AdditionalEffect {
  effect: string;
  chance: number;
}

/** The Move fields the Ruleset can override (the full keyed record, field by
    field). `overridden_fields` lists the subset the Ruleset actually changed. */
export type MoveField =
  | "name"
  | "type"
  | "category"
  | "power"
  | "accuracy"
  | "pp"
  | "description"
  | "effect"
  | "argument"
  | "additional_effects"
  | "flags"
  | "priority"
  | "target";

/** Pre-override base values for whatever the Ruleset changed (base → now diff).
    Empty (`{}`) for a Ruleset-created move that has no base to diff against. */
export interface MoveBaseValues {
  name?: string;
  type?: string;
  category?: "physical" | "special" | "status";
  power?: number | null;
  accuracy?: number | null;
  pp?: number | null;
  description?: string;
  effect?: string;
  argument?: Record<string, unknown> | null;
  additional_effects?: AdditionalEffect[];
  flags?: string[];
  priority?: number;
  target?: string;
}

/** The merged base ⊕ Ruleset view of one move, mirroring {@link DexEntry} and
    {@link Ability}. `GET /api/moves` and `GET /api/targets/{id}/moves` return
    these. */
export interface Move {
  name: string;
  chrooked_id: string;
  /** Engine symbol(s); carried through edits so apply (M3) keeps resolving. */
  aka: Record<string, unknown>;
  type: string;
  category: "physical" | "special" | "status";
  power: number | null;
  accuracy: number | null;
  pp: number | null;
  description: string;
  effect: string;
  argument: Record<string, unknown> | null;
  additional_effects: AdditionalEffect[];
  flags: string[];
  priority: number;
  target: string;
  /** The fields the Ruleset changed. `[]` ⇒ base-only (not edited). */
  overridden_fields: MoveField[];
  /** Pre-override base values for the changed fields. `{}` for a created entry. */
  base: MoveBaseValues;
}

/** The writable shape sent on PUT — the Ruleset owns the move record, but the
    merge-view flags (`overridden_fields`, `base`) are server-recomputed and the
    move loader REJECTS them as unknown keys (422), so they must be stripped. */
export type MoveWrite = Omit<Move, "overridden_fields" | "base">;

/** The Ability fields the Ruleset can override (name, description). */
export type AbilityField = "name" | "description";

/** Pre-override base values for whatever the Ruleset changed (base → now diff).
    Empty (`{}`) for a Ruleset-created ability that has no base to diff against. */
export interface AbilityBaseValues {
  name?: string;
  description?: string;
}

/** The merged base ⊕ Ruleset view of one ability, mirroring {@link DexEntry}.
    `GET /api/abilities` and `GET /api/targets/{id}/abilities` return these. */
export interface Ability {
  name: string;
  chrooked_id: string;
  description: string;
  /** Engine symbol(s); carried through edits so apply (M3) keeps resolving. */
  aka: Record<string, unknown>;
  /** The fields the Ruleset changed. `[]` ⇒ base-only (not edited). */
  overridden_fields: AbilityField[];
  /** Pre-override base values for the changed fields. `{}` for a created entry. */
  base: AbilityBaseValues;
}

/** The writable shape sent on PUT — the Ruleset owns only these fields. The
    merge-view flags (`overridden_fields`, `base`) are server-recomputed and the
    ability loader REJECTS them as unknown keys (422), so they must be stripped. */
export type AbilityWrite = Omit<Ability, "overridden_fields" | "base">;

/** The write shape for the type-chart PUT: only the override set (cells whose
    multiplier differs from base). One whole-list file → a write replaces it. */
export interface TypeChartEntry {
  attacker: string;
  defender: string;
  multiplier: number;
}

/** One attacker×defender cell of the FULL merged grid (base ⊕ Ruleset), as
    returned by `GET /api/type-chart` and `GET /api/targets/{id}/type-chart`.
    `overridden` ⇒ the Ruleset changed this pair; `base_multiplier` is the
    pre-override value when overridden, null otherwise. Mirrors {@link Move}'s
    base→now diff contract, but per-cell across the N×N matrix. */
export interface TypeChartCell {
  attacker: string;
  defender: string;
  multiplier: number;
  overridden: boolean;
  base_multiplier: number | null;
}

export interface BehaviorEffect {
  summary: string;
  trigger: string;
  effect: string;
  when: string | null;
}

export interface BehaviorTestCase {
  given: string;
  expect: string;
}

export interface Behavior {
  name: string;
  chrooked_id: string;
  applies_to: "ability" | "move";
  /** Engine symbol(s); carried through edits so apply (M3) keeps resolving. */
  aka: Record<string, unknown>;
  effects: BehaviorEffect[];
  test_cases: BehaviorTestCase[];
  notes: string[];
  engine_hints: Record<string, string>;
}

/** The tab keys, also used as URL state. "targets" is the apply panel (M3);
    the rest are the read-only / Ruleset-edit surfaces. */
export type KindKey =
  | "dex"
  | "moves"
  | "abilities"
  | "type-chart"
  | "behaviors"
  | "targets"
  | "ledger";

/** The engines a Target fork can be (only pokeemerald applies end-to-end in M3;
    essentials is recorded for later). */
export type EngineKey = "pokeemerald" | "essentials";

/** A registered game fork the Ruleset can be previewed against or applied to. */
export interface Target {
  id: string;
  label: string;
  /** Absolute path to the fork, resolved on the server when added. */
  path: string;
  engine: EngineKey;
  /** The committed Target Override namespace slug this fork is bound to, or null.
      Scoped edits land under `ruleset/targets/<namespace>/`. */
  namespace: string | null;
}

/** A Target's bound Override namespace, from `GET /api/targets/{id}/namespace`. */
export interface TargetNamespace {
  slug: string;
  engine: EngineKey;
  label: string;
}

/** One Change Ledger entry. `fields` is a per-field `from → to` diff (edits and
    harvest); `report` carries Apply Report counts (apply events); `summary` holds
    bulk seed counts. `scope` is "base" or "target:<slug>". */
export interface LedgerEntry {
  ts: string;
  scope: string;
  kind: string;
  chrooked_id: string | null;
  source: "web-edit" | "harvest" | "apply" | "seed";
  fields?: Record<string, { from: unknown; to: unknown }>;
  report?: { applied: number; partial: number; blocked: number };
  blocked_entries?: { chrooked_id: string; reason: string }[];
  summary?: Record<string, number>;
  fork?: string;
}

/** The detected PBS dialect of a registered Target.
    ``dialect`` is ``"essentials16"`` or ``"essentials21"`` for Essentials targets,
    ``null`` for pokeemerald (engine does not have a dialect) or when detection
    fails (unrecognized format).  ``label`` is the display string ("16.2",
    "v19+ (modern)"), or ``null`` when ``dialect`` is ``null``. */
export interface TargetDialect {
  dialect: string | null;
  label: string | null;
}

/** A DATA-ONLY created ability in an Apply Report: a record whose mechanic lives
    only in a behavior packet, with a link to that packet's markdown. */
export interface DataOnlyEntry {
  chrooked_id: string;
  symbol: string;
  /** The packet endpoint URL (GET → {@link BehaviorPacket}). */
  packet_url: string;
}

/** The result of a preview or apply: the four headline counts, the DATA-ONLY
    list, and the full markdown report. Shared by both endpoints. */
export interface ApplyReportSummary {
  applied: number;
  partial: number;
  blocked: number;
  created: number;
  data_only: DataOnlyEntry[];
  report_md: string;
}

/** The markdown packet for one behavior, fetched on demand from a DATA-ONLY
    entry's `packet_url`. */
export interface BehaviorPacket {
  chrooked_id: string;
  markdown: string;
}
