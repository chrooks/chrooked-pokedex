"""Render behavior specs into human/agent-readable Markdown.

Two outputs:

  * the **manifest** — every mechanic in the Ruleset, so you can see at a glance what a
    target engine must implement;
  * a **packet** — one mechanic rendered as a self-contained implementation brief: intent,
    neutral triggers, edge cases, the target-engine hint, and the test cases that define
    "correct". A packet is meant to be handed to Claude (or a person) with no prior
    context about this Ruleset.
"""

from __future__ import annotations

from ..model import Ruleset
from ..model.behavior_spec import BehaviorSpec


def render_manifest(ruleset: Ruleset) -> str:
    """One line per mechanic: what must exist in any target engine."""
    specs = sorted(ruleset.behaviors.values(), key=lambda s: s.chrooked_id)
    lines = ["# Behavior manifest", ""]
    if not specs:
        lines.append("_No behavior specs. Nothing custom to implement._")
        return "\n".join(lines) + "\n"

    lines.append(f"{len(specs)} mechanic(s) the target engine must implement:")
    lines.append("")
    lines.append("| chrooked_id | name | applies to | effects | tests |")
    lines.append("| --- | --- | --- | --- | --- |")
    for spec in specs:
        lines.append(
            f"| {_cell(spec.chrooked_id)} | {_cell(spec.name)} "
            f"| {_cell(spec.applies_to)} | {len(spec.effects)} | {len(spec.test_cases)} |"
        )
    return "\n".join(lines) + "\n"


def _cell(value: str) -> str:
    """Escape a value for a Markdown table cell so a stray pipe cannot break the row."""
    return value.replace("|", "\\|")


def render_packet(spec: BehaviorSpec, engine: str | None = None) -> str:
    """A self-contained implementation brief for one mechanic.

    `engine` selects which engine hint to surface (e.g. "pokeemerald"); when omitted or
    absent from the spec, every hint is listed so the implementer can pick.

    Spec field values are emitted verbatim into Markdown prose. The YAML loader is the
    Boundary that should reject malformed specs; specs are human-authored and in-repo.
    """
    lines = [
        f"# Implement: {spec.name}",
        "",
        f"- chrooked_id: `{spec.chrooked_id}`",
        f"- applies to: {spec.applies_to}",
    ]
    if spec.aka:
        aka = ", ".join(f"{k}={v}" for k, v in spec.aka.items())
        lines.append(f"- known as: {aka}")
    lines += ["", "## What it does", ""]
    for effect in spec.effects:
        gate = f" _(when {effect.when})_" if effect.when else ""
        lines.append(f"- **{effect.summary}**{gate}")
        lines.append(f"  - trigger: `{effect.trigger}`")
        lines.append(f"  - effect: {effect.effect}")

    if spec.notes:
        lines += ["", "## Edge cases", ""]
        lines += [f"- {note}" for note in spec.notes]

    lines += ["", "## Engine hint", ""]
    lines += _engine_hint_lines(spec, engine)

    lines += ["", "## Acceptance tests (the mechanic is correct only if all pass)", ""]
    if spec.test_cases:
        for index, case in enumerate(spec.test_cases, start=1):
            lines.append(f"{index}. Given {case.given}, expect: {case.expect}.")
    else:
        lines.append("_No test cases authored — add them before trusting an implementation._")
    return "\n".join(lines) + "\n"


def _engine_hint_lines(spec: BehaviorSpec, engine: str | None) -> list[str]:
    if not spec.engine_hints:
        return ["_No engine hint provided._"]
    if engine is not None:
        hint = spec.engine_hints.get(engine)
        if hint is not None:
            return [f"- **{engine}**: {hint}"]
        return [
            f"_No hint for engine {engine!r}. Available hints:_",
            *[f"- **{name}**: {text}" for name, text in spec.engine_hints.items()],
        ]
    return [f"- **{name}**: {text}" for name, text in spec.engine_hints.items()]
