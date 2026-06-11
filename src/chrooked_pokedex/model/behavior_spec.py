"""Engine-neutral behavior specs for custom mechanics.

The Ruleset's data layer carries *what* an ability or move is; this layer carries *how* it
behaves, as a portable specification a context-aware implementer (Claude) compiles to a
specific engine. It is deliberately NOT data the deterministic applier writes — engine
battle logic differs per engine and per version and cannot travel as data.

Behavior specs are **human-owned** and live in their own `ruleset/behaviors/` folder,
physically apart from the **machine-owned** data the seed regenerates. The seed writer
clears and rewrites `species/`, `moves/`, and `abilities/` on every run; it never touches
`behaviors/`, so a hand-authored spec is safe across re-seeds.

What keeps a spec reliable rather than vague prose:

  * every effect attaches to one of a small, neutral set of battle TRIGGERS — the hook
    points that exist in any turn-based Pokemon engine (the Seams behavior attaches to);
  * each behavior carries concrete test cases — the Contract that lets whatever the agent
    generates be verified instead of trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional


# The neutral battle hooks an effect can attach to. These are inherent to a turn-based
# Pokemon battle loop, not to any one engine, so a spec written against them stays
# portable across pokeemerald-expansion (C) and Pokemon Essentials (Ruby).
TRIGGERS: frozenset[str] = frozenset(
    {
        "switch-in",      # the Pokemon enters the field
        "turn-order",     # move order / priority is decided
        "accuracy-check", # whether a move hits is rolled
        "damage-calc",    # outgoing/incoming damage is computed
        "on-hit",         # a move connects
        "on-contact",     # a contact move connects
        "status-apply",   # a status/volatile condition would be applied
        "stat-change",    # a stat stage would change
        "turn-end",       # end-of-turn resolution
        "faint",          # the Pokemon faints
    }
)

# What a behavior spec attaches to.
APPLIES_TO: frozenset[str] = frozenset({"ability", "move"})


@dataclass(frozen=True)
class BehaviorEffect:
    """One discrete effect of a mechanic, attached to a neutral trigger.

    `when` is an optional plain-language condition that gates the effect (e.g. "the move
    being used is Focus Blast"); absent means the effect always applies at its trigger.
    """

    summary: str
    trigger: str
    effect: str
    when: Optional[str] = None


@dataclass(frozen=True)
class BehaviorTestCase:
    """A concrete acceptance scenario: the Contract an implementation must satisfy."""

    given: str
    expect: str


@dataclass(frozen=True)
class BehaviorSpec:
    """The full behavior spec for one ability or move.

    The spec is self-identifying (name, chrooked_id, aka) so it is portable on its own and
    can attach to a *vanilla* ability the data layer does not own (e.g. Inner Focus) just
    as well as to a Ruleset-owned one. An entity can have several effects — a vanilla one
    plus a custom addition, say. `engine_hints` maps an engine name to an optional pointer
    for the implementer; `notes` records interactions and edge cases.
    """

    name: str
    chrooked_id: str
    applies_to: str
    aka: Mapping[str, object] = field(default_factory=dict)
    effects: tuple[BehaviorEffect, ...] = ()
    test_cases: tuple[BehaviorTestCase, ...] = ()
    notes: tuple[str, ...] = ()
    engine_hints: Mapping[str, str] = field(default_factory=dict)
