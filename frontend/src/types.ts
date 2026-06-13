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
  overridden_fields: OverridableField[];
  base: DexBaseValues;
}

export interface AdditionalEffect {
  effect: string;
  chance: number;
}

export interface Move {
  name: string;
  chrooked_id: string;
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
}

export interface Ability {
  name: string;
  chrooked_id: string;
  description: string;
}

export interface TypeChartEntry {
  attacker: string;
  defender: string;
  multiplier: number;
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
  effects: BehaviorEffect[];
  test_cases: BehaviorTestCase[];
  notes: string[];
  engine_hints: Record<string, string>;
}

/** The five read-only surfaces, used as tab keys and URL state. */
export type KindKey = "dex" | "moves" | "abilities" | "type-chart" | "behaviors";
