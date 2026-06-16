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

export interface Evolution {
  from: string | null;
  method: Record<string, unknown>;
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
  /** True when the species has no outgoing evolution (a final form or a
      single-stage mon). A base fact from the snapshot; drives the Fully Evolved
      class. */
  fully_evolved: boolean;
  overridden_fields: OverridableField[];
  base: DexBaseValues;
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
  | "targets";

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
