"""Essentials acceptance-test harness (Route B: log oracle).

The Essentials 16.2 battle engine cannot be run headlessly (its ``PokeBattle_Battle``
constructor needs a full on-screen scene + parties — see issue #15 / M0), so the
oracle is a log file: each ``# chrooked:<id>`` plugin writes a uniform
``[chrooked:<id>] OBS key=value ...`` line on the battle event it gates, and this
driver reads those lines back and scores them against the mechanic's neutral
``test_cases``.

Flow (play-one-battle):

    python -m chrooked_pokedex.behavior.harness stage  innerfocus   # clears the log, prints what to do in-game
    # ... boot the game, run the debug battle as instructed, quit ...
    python -m chrooked_pokedex.behavior.harness verify innerfocus   # reads the log, prints PASS/FAIL per test_case

The driver is mechanic-agnostic: everything specific lives in the mechanic's
plugin (what it logs) and its entry in ``harness_scenarios.py`` (which
observation proves each test_case). Reported wording comes from the spec's own
``test_cases`` so the harness verifies the Contract, not a paraphrase.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ..model import Ruleset
from .harness_scenarios import SCENARIOS

# One observation the plugin logged, e.g. "[chrooked:innerfocus] OBS move=FOCUSBLAST if=true result=ALWAYS_HIT".
_OBS_RE = re.compile(r"^\[chrooked:(?P<id>[^\]]+)\]\s+OBS\s+(?P<kv>.+)$")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RULESET_DIR = _REPO_ROOT / "ruleset"
_TARGETS_JSON = _REPO_ROOT / "targets.json"
_LOG_RELPATH = Path("Scripts") / "chrooked_load.log"


def parse_observations(log_text: str, mechanic_id: str) -> list[dict[str, str]]:
    """Extract this mechanic's OBS lines, newest-relevant first kept in order.

    Each returned dict is the flat key/value pairs of one observation. Lines for
    other mechanics, and any non-OBS log noise, are ignored.
    """
    observations: list[dict[str, str]] = []
    for line in log_text.splitlines():
        match = _OBS_RE.match(line.strip())
        if not match or match.group("id") != mechanic_id:
            continue
        fields: dict[str, str] = {}
        for token in match.group("kv").split():
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key] = value
        observations.append(fields)
    return observations


def _match(observation: dict[str, str], criteria: dict[str, object]) -> bool:
    """True when every criterion key equals the observation's value (as strings)."""
    return all(str(observation.get(key)) == str(value) for key, value in criteria.items())


def score(observations: list[dict[str, str]], checks: list[dict[str, object]],
          test_cases: tuple) -> list[dict[str, object]]:
    """Score each check against the observations; return per-case results.

    A case fails if no observation matches its ``select`` (the staged action was
    not seen) or if the matching observation violates ``expect``.
    """
    results: list[dict[str, object]] = []
    for index, check in enumerate(checks):
        given = test_cases[index].given if index < len(test_cases) else f"case {index + 1}"
        select = check.get("select", {})  # type: ignore[assignment]
        expect = check.get("expect", {})  # type: ignore[assignment]
        hit = next((o for o in observations if _match(o, select)), None)  # type: ignore[arg-type]
        if hit is None:
            results.append({"passed": False, "given": given,
                            "reason": f"not observed (no OBS matching {select}); was the action staged?"})
        elif _match(hit, expect):  # type: ignore[arg-type]
            results.append({"passed": True, "given": given, "reason": ""})
        else:
            results.append({"passed": False, "given": given,
                            "reason": f"expected {expect}, observed {hit}"})
    return results


def _resolve_target(explicit: str | None) -> Path:
    """Pick the Essentials target: explicit path, else the essentials entry in targets.json."""
    if explicit:
        return Path(explicit)
    if not _TARGETS_JSON.exists():
        raise SystemExit(f"no --target and no targets.json at {_TARGETS_JSON}")
    targets = json.loads(_TARGETS_JSON.read_text())
    pick = next((t for t in targets if t.get("engine") == "essentials"), None)
    if not pick:
        raise SystemExit("no essentials target in targets.json (pass --target)")
    return Path(pick["path"])


def _load_checks(mechanic_id: str, ruleset_dir: Path) -> tuple[list[dict[str, object]], tuple]:
    """Return (scenario checks, spec test_cases), failing loudly if they are out of sync."""
    if mechanic_id not in SCENARIOS:
        raise SystemExit(f"no harness scenario for '{mechanic_id}' (add one in harness_scenarios.py)")
    ruleset = Ruleset.load(ruleset_dir)
    if mechanic_id not in ruleset.behaviors:
        raise SystemExit(f"no behavior spec '{mechanic_id}' in {ruleset_dir}/behaviors")
    spec = ruleset.behaviors[mechanic_id]
    checks = SCENARIOS[mechanic_id]
    if len(checks) != len(spec.test_cases):
        raise SystemExit(
            f"scenario for '{mechanic_id}' has {len(checks)} checks but the spec has "
            f"{len(spec.test_cases)} test_cases — keep them aligned 1:1.")
    return checks, spec.test_cases


def cmd_stage(mechanic_id: str, ruleset_dir: Path, target: Path) -> int:
    """Clear the log and print the in-game actions that produce this mechanic's observations."""
    checks, _ = _load_checks(mechanic_id, ruleset_dir)
    log_path = target / _LOG_RELPATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("")  # fresh session
    print(f"Staged '{mechanic_id}'. Log cleared: {log_path}")
    print("Boot the game (debug), start a debug battle, then do IN ORDER:\n")
    for index, check in enumerate(checks, start=1):
        print(f"  {index}. {check.get('stage')}")
    print(f"\nThen quit and run:  python -m chrooked_pokedex.behavior.harness verify {mechanic_id}")
    return 0


def cmd_verify(mechanic_id: str, ruleset_dir: Path, target: Path) -> int:
    """Read the log and print PASS/FAIL per test_case; exit non-zero on any failure."""
    checks, test_cases = _load_checks(mechanic_id, ruleset_dir)
    log_path = target / _LOG_RELPATH
    if not log_path.exists():
        raise SystemExit(f"no log at {log_path} — run `stage` and play the battle first")
    results = score(parse_observations(log_path.read_text(), mechanic_id), checks, test_cases)
    passed = 0
    for result in results:
        tag = "PASS" if result["passed"] else "FAIL"
        line = f"{tag} {mechanic_id} :: {result['given']}"
        if not result["passed"]:
            line += f"  ({result['reason']})"
        print(line)
        passed += 1 if result["passed"] else 0
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description="Essentials behavior-port acceptance harness (log oracle).")
    parser.add_argument("command", choices=["stage", "verify"])
    parser.add_argument("mechanic", help="chrooked_id, e.g. innerfocus")
    parser.add_argument("--target", help="Essentials target path (default: essentials entry in targets.json)")
    parser.add_argument("--ruleset", help="Ruleset dir (default: repo ruleset/)")
    args = parser.parse_args(argv)

    ruleset_dir = Path(args.ruleset) if args.ruleset else _RULESET_DIR
    target = _resolve_target(args.target)
    if args.command == "stage":
        return cmd_stage(args.mechanic, ruleset_dir, target)
    return cmd_verify(args.mechanic, ruleset_dir, target)


if __name__ == "__main__":
    sys.exit(main())
