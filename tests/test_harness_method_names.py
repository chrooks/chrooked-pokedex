"""Guard against calling a battler method Rejuv does not define.

`chrooked_zz_spikyshield.rb` shipped `user.fainted?` — Rejuv spells it
`isFainted?` — and crashed mid-battle on 2026-09-17. Ruby only raises on the
line it runs, so a typo in a rarely-hit branch reaches the player. This is a
static scan: every method called on a battler-ish receiver in the harness must
be defined somewhere in the target's Scripts/, in the harness itself, or be a
Ruby built-in.

Integration-marked: it needs the real on-disk Rejuv checkout.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent.parent / "references" / "rejuv-harness"
GAME_SCRIPTS = Path("/home/chrooks/projects/rejuv-game/Scripts")

# Receivers that are battler/Pokemon objects in the harness's own idiom.
_RECEIVER = r"\b(?:user|battler|target|attacker|opponent|poke|mon)\."
_CALL = re.compile(_RECEIVER + r"([A-Za-z_]\w*[?!]?)")
_DEF = re.compile(r"def\s+(?:self\.)?([A-Za-z_]\w*[?!=]?)")
_ATTR = re.compile(r"attr_(?:accessor|reader|writer)\s+(.+)")

# Ruby methods every object has; kept explicit so the test needs no ruby binary.
_RUBY_BUILTINS = frozenset("""
    class clone dup freeze frozen? hash inspect is_a? kind_of? instance_of? nil?
    respond_to? send public_send object_id tap then itself to_s to_a to_i to_f
    == != === equal? eql? instance_variable_get instance_variable_set
    instance_variables method methods display extend
""".split())


def _defined_names(text: str) -> set[str]:
    names = set(_DEF.findall(text))
    for match in _ATTR.finditer(text):
        names |= set(re.findall(r":(\w+)", match.group(1)))
    return names


@pytest.mark.integration
def test_harness_calls_only_methods_the_game_defines() -> None:
    if not GAME_SCRIPTS.is_dir():
        pytest.skip(f"no Rejuv checkout at {GAME_SCRIPTS}")

    known = set(_RUBY_BUILTINS)
    for path in GAME_SCRIPTS.rglob("*.rb"):
        known |= _defined_names(path.read_text(encoding="utf-8", errors="replace"))
    for path in HARNESS.glob("*.rb"):
        known |= _defined_names(path.read_text(encoding="utf-8", errors="replace"))

    unknown: list[str] = []
    for path in sorted(HARNESS.glob("chrooked_*.rb")):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if line.lstrip().startswith("#"):
                continue
            for match in _CALL.finditer(line):
                if match.group(1) not in known:
                    unknown.append(f"{path.name}:{lineno}: {match.group(0)}")

    assert not unknown, (
        "harness calls methods Rejuv does not define (these crash mid-battle):\n  "
        + "\n  ".join(unknown)
    )
