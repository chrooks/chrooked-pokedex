# Design a Pokémon Essentials applier for the chrooked-pokedex Ruleset

This is a design note, not an implementation. It exists so the next session can
start building the Essentials applier from the Ruleset as it already is, without
re-deriving the mapping. It must be maintained in accordance with the ExecPlan
rules in `/Users/cdbrooks/.claude/PLAN.md`. No code is written in this milestone;
the acceptance is that this file exists and describes the per-category mapping and
the parts that cannot be expressed as flat data.

## Purpose / Big Picture

Today the Ruleset (the engine-neutral set of Chris's preferred Pokémon changes, a
folder of YAML under `ruleset/`) has one working applier, for pokeemerald-expansion
forks, which writes C. The other target Chris wants is Pokémon Essentials: a fan
game engine built in Ruby on RPG Maker XP. Most Essentials game data lives in
plain text files called PBS files (PBS = "Pokémon Battle System", the historical
name), for example `pokemon.txt`, `moves.txt`, `abilities.txt`, `types.txt`. PBS
text is far easier to write than C. The good news this note records: the neutral
schema maps onto PBS almost one-for-one for data. The hard part, called out
explicitly below, is that a brand-new ability or move's *behavior* is Ruby code,
which flat PBS data cannot express.

When the Essentials applier is built, running it against a copy of an Essentials
game's `PBS/` folder will rewrite that game's `pokemon.txt`, `moves.txt`,
`abilities.txt`, and `types.txt` so that Goodra is Water/Dragon, Aegislash can
learn the custom move Excalibur, Ice resists Flying, and so on — with the same
Apply Report contract the pokeemerald applier already prints: every entry applied,
blocked, or partial, nothing silently dropped.

## Orientation: how Essentials PBS files are shaped

A novice needs these facts; they are stated here so this note is self-contained.

Modern Essentials (v20+/v21) PBS files are sectioned INI-like text. Each record is
a header in square brackets followed by `Key = Value` lines. The identifier in the
header is the engine's internal symbol — the analogue of pokeemerald's
`SPECIES_GOODRA`. A species record in `pokemon.txt` looks like this:

    [GOODRA]
    Name = Goodra
    Types = DRAGON
    BaseStats = 90,100,70,80,110,150
    Abilities = SAPSIPPER,HYDRATION
    HiddenAbility = GOOEY
    Moves = 1,TACKLE,1,BUBBLE,30,LIQUIDATION,45,DRAGONBREATH
    # ... many other keys (EVs, GrowthRate, Evolutions, etc.)

A move record in `moves.txt`:

    [EXCALIBUR]
    Name = Excalibur
    Type = STEEL
    Category = Physical
    Power = 90
    Accuracy = 100
    TotalPP = 10
    Target = NearOther
    FunctionCode = None
    Flags = Contact,Protectable
    Description = A holy sword strike.

An ability record in `abilities.txt`:

    [POISONHEAL]
    Name = Poison Heal
    Description = Restores HP if the bearer is poisoned.

A type record in `types.txt` (effectiveness is expressed from the *defender's*
point of view, as lists of the attacking types it is weak/resistant/immune to):

    [ICE]
    Name = Ice
    Weaknesses = FIRE,FIGHTING,ROCK,STEEL
    Resistances = ICE
    Immunities =

The key structural difference from pokeemerald: the type chart is not a matrix in
one file; it is distributed across type records as Weaknesses/Resistances/
Immunities lists. A multiplier override therefore edits the *defender's* record.

## The neutral schema, recalled

The Ruleset's shapes (defined in `src/chrooked_pokedex/model/schema.py`) are:
`SpeciesOverride` (name, chrooked_id, aka, types, abilities {primary, secondary,
hidden}, stats {hp, atk, def, spa, spd, spe}, learnset = whole list of {level,
move}, evolution), `MoveDef` (name, chrooked_id, type, category, power, accuracy,
pp, description, aka), `AbilityDef` (name, chrooked_id, description, aka), and
`TypeChartOverride` (attacker, defender, multiplier). Every entity carries a
`chrooked_id` and may carry `aka` hints. The pokeemerald applier added
`aka.pokeemerald`; the Essentials applier will read (and the seed/harvest can
record) `aka.essentials` for the PBS identifier.

## Per-category mapping (data — the easy 95%)

Species name. The neutral `name` maps to the PBS `Name =` line; the `chrooked_id`
maps to the bracket identifier `[GOODRA]`, resolved through the Resolution map
exactly as `chrooked_id -> SPECIES_GOODRA` works for pokeemerald. The default
construction is `chrooked_id.upper()` with non-alphanumerics removed
(`mrmime -> MRMIME`), confirmed or overridden by `aka.essentials`.

Types. Neutral type names map to PBS type identifiers by uppercasing: `Water ->
WATER`, `Dragon -> DRAGON`. A single type is written `Types = DRAGON`; two types
`Types = WATER,DRAGON`. Whole-field replacement, same as the pokeemerald applier.

Abilities. The neutral `abilities.primary`/`secondary` map to the comma list
`Abilities = PRIMARY,SECONDARY`; `abilities.hidden` maps to the separate
`HiddenAbility =` key. Ability identifiers are the display name uppercased with
spaces removed: `Poison Heal -> POISONHEAL`. Because the Ruleset stores only the
changed slots, the applier reads the record's current `Abilities`/`HiddenAbility`,
overlays the changed slots, and rewrites — the same per-slot overlay the
pokeemerald applier does, and subject to the same lesson learned there (overlay,
do not blindly replace the whole list, or unchanged slots are lost).

Stats. The neutral stat keys map into the single positional `BaseStats =` line,
whose order is HP, Attack, Defense, Speed, Sp. Atk, Sp. Def — note Speed is third
in PBS, unlike pokeemerald's field order. The applier reads the current six,
substitutes the overridden ones by position, and rewrites the line. This is the
one place a positional gotcha bites; the mapping `{hp:0, atk:1, def:2, spe:3,
spa:4, spd:5}` must be encoded explicitly.

Learnsets. The neutral whole-list learnset maps to the single `Moves =` line as a
flat `level,MOVE,level,MOVE,...` sequence. Because the Ruleset owns the whole list
(the decision that fixed v1's duplicate-move bug), the applier replaces the entire
`Moves =` line — no merge — which is structurally simpler in PBS than in C because
there is exactly one line, not one array per generation.

Moves (Ruleset-owned). A `MoveDef` becomes a `moves.txt` record. `type ->
Type =` (uppercased), `category` (physical/special/status) -> `Category =`
(Physical/Special/Status, capitalized), `power -> Power =`, `accuracy ->
Accuracy =`, `pp -> TotalPP =`, `description -> Description =`. Creation here is
appending a new bracket record, the PBS analogue of the pokeemerald applier
appending a `MOVE_*` constant and data entry — and easier, because PBS has no
count sentinel to bump.

Abilities (Ruleset-owned). An `AbilityDef` becomes an `abilities.txt` record with
`Name =` and `Description =`.

Type chart. Each `TypeChartOverride(attacker, defender, multiplier)` edits the
*defender's* record in `types.txt`, because Essentials stores effectiveness on the
defender. The mapping from multiplier to list membership:

    multiplier 0    -> add attacker to Immunities,  remove from Weaknesses/Resistances
    multiplier 0.5  -> add attacker to Resistances,  remove from Weaknesses/Immunities
    multiplier 1    -> remove attacker from all three lists (neutral)
    multiplier 2    -> add attacker to Weaknesses,    remove from Resistances/Immunities

So Chris's Flying-resisted-by-Ice override (`attacker: Flying, defender: Ice,
multiplier: 0.5`) adds `FLYING` to Ice's `Resistances =` list. This is a
read-modify-write on one list, not a matrix cell edit.

Evolutions. The neutral `evolution.from` (a backward pointer: this species evolves
*from* a pre-evolution) maps to the pre-evolution's `Evolutions =` line, which in
PBS is `SPECIES,METHOD,PARAMETER` triples — the same inversion the pokeemerald
evolution applier already performs. As in pokeemerald, this is only as complete as
the method vocabulary the applier chooses to support, and the real seeded Ruleset
currently carries no evolution data.

## What cannot be expressed as flat PBS data (the hard 5%)

Everything above is data and lands as text. The boundary is *behavior*.

Custom move and ability behavior is Ruby, not data. A `moves.txt` record has a
`FunctionCode =` key naming the Ruby effect that runs the move's special logic
(for example a move that always lands a critical hit, or heals the user). A flat
record can set `FunctionCode = None` and the move will exist, be selectable, and
deal its typed damage — but any non-standard effect requires a Ruby handler
defined in the game's scripts (historically `PBEffects`/`Battle::Move` subclasses,
in modern Essentials a `Battle::Move::FunctionName` class). Abilities are the same:
`abilities.txt` gives an ability a name and description, but its in-battle effect
is Ruby hooked into the battle engine. The Ruleset today stores an ability's name
and description and nothing about its mechanics, so the Essentials applier can
create the *record* but cannot create the *behavior*.

Concretely for Chris's data: Excalibur can be created as a Steel physical move and
taught to Aegislash from PBS alone, and it will work as a plain typed attack. If
Excalibur is meant to do something special (the way the seeded pokeemerald data
hints with "super effective on Dragons"), that special rule is Ruby the applier
cannot synthesize from the current schema. The same is true of any
Ruleset-invented ability such as Striker.

The honest report contract carries over: when the Essentials applier creates a
move or ability whose intended behavior is non-trivial, it should mark the entry
`partial` in the Apply Report with a reason like "record created; behavior
FunctionCode requires Ruby", rather than implying the effect landed. Nothing
silently dropped, and nothing silently faked.

A second, smaller boundary: the Ruleset's neutral type names and the target game's
type roster must line up. A fan game with a custom type the Ruleset references, or
missing a type the Ruleset names, is the same blocked/partial situation the
pokeemerald applier already handles — surfaced loudly, not guessed.

## Suggested first Vertical Slice when this is built

Mirror how the pokeemerald applier was grown. The smallest end-to-end slice is the
species scalar push: parse `pokemon.txt` into records, build the Resolution map
(`chrooked_id -> [IDENTIFIER]` from `aka.essentials` plus the file's own headers),
rewrite `Types`/`Abilities`/`HiddenAbility`/`BaseStats` for overridden species with
whole-field replacement, and print the Apply Report — then add learnsets (one-line
whole-list replace), then `types.txt` overrides, then owned-record creation in
`moves.txt`/`abilities.txt`, ending where the boundary is: FunctionCode behavior
stays Ruby and is reported, not invented.

## Progress

- [x] (2026-06-11) Design note written: per-category PBS mapping and the
  behavior-needs-Ruby boundary documented. No code, by design.

## Decision Log

- Decision: the Essentials type-chart override edits the defender's record's
  Weaknesses/Resistances/Immunities lists, not a matrix cell.
  Rationale: Essentials stores effectiveness on the defender; there is no matrix.
  Date/Author: 2026-06-11, Chris + Claude.

- Decision: creating an owned move/ability in Essentials writes the PBS record and
  reports `partial` when non-trivial behavior (FunctionCode/Ruby) is implied.
  Rationale: flat PBS cannot express behavior; the no-silent-drop contract requires
  surfacing the gap rather than shipping an inert move as if complete.
  Date/Author: 2026-06-11, Chris + Claude.

## Outcomes & Retrospective

The neutral schema maps cleanly onto Essentials PBS for all data categories, with
two positional/structural gotchas to encode (BaseStats order; defender-side type
chart) and one true boundary (custom behavior is Ruby). No schema change is needed
to begin the Essentials data applier; behavior modeling, if ever wanted, would be a
future schema extension, not a blocker for this work.
