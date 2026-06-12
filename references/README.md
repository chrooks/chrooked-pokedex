# Reference implementations

Per-engine, per-version implementations of Ruleset **behaviors**. The Ruleset itself stays
engine-neutral; these `.patch` files are the engine-specific output of porting a
[behavior spec](../ruleset/behaviors/) into a real target.

They are a **growing library**: the first time a mechanic is implemented for an engine, the
diff is captured here. The next time that engine is targeted, the port is near-mechanical
reuse instead of a fresh derivation.

## Naming

`<chrooked_id>.<engine>-<version>.patch` — e.g. `innerfocus.pokeemerald-expansion-1.15.3.patch`.

Apply with `git apply <file>` from the target fork's root (the path is relative to repo root).

## How each was produced

The behavior-port loop:

1. `chrooked-pokedex behaviors --mechanic <id> --engine <engine>` emits a self-contained packet.
2. A behavior-port agent implements it into a clean target **from the packet only**.
3. The edit is static-verified against the spec's acceptance tests and compiled.
4. The diff is captured here.

A reference patch carries BOTH the mechanic edit AND, for pokeemerald, its battle test —
the executable form of the spec's acceptance cases. Verification is RED→GREEN: the test
fails on the clean engine (proving it exercises the mechanic), then passes once the mechanic
is applied.

## Inventory

| mechanic | engine | verified |
| --- | --- | --- |
| innerfocus | pokeemerald-expansion 1.15.3 | `make check` RED→GREEN (battle test) + compiles |

### innerfocus.pokeemerald-expansion-1.15.3

- **Seam:** `CanMoveSkipAccuracyCalc` in `src/battle_util.c` — 1.15.3's dedicated predicate
  for every "always hit" condition.
- **Note:** the agent chose this Seam over the sibling reference fork's older inline
  `return TRUE` in `GetTotalAccuracy`, by reading the 1.15.3 engine. The dumb patch-apply
  would have been wrong; the spec + engine knowledge produced a *better* port.
- Gated on the attacker's own `ABILITY_INNER_FOCUS` and `MOVE_FOCUS_BLAST` only, so it does
  not leak to other moves or to non-Inner-Focus users, and Mold Breaker (a target-bypass)
  cannot suppress it.
- **Battle test:** `test/battle/ability/inner_focus.c` gains three `SINGLE_BATTLE_TEST`s.
  The discriminator — *"Inner Focus makes the user's Focus Blast always hit"* — uses
  `PASSES_RANDOMLY(100, 100, RNG_ACCURACY)` on a 70%-base move. On the clean engine it
  failed at the true `0.69` hit rate; with the mechanic it passes 100/100. The other two
  assert the bypass does not leak to other moves or non-Inner-Focus users.
