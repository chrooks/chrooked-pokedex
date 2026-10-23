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

Essentials 21 targets (``references/essentials21-harness/``) use the same OBS
lines with two layout differences: the log sits in the game folder
(``chrooked_load.log``), and ports write it only while ``chrooked-oracle.on``
exists there at boot, so ``stage`` sets that marker. Their AI-estimate lines are
tagged ``EST`` and never scored. A lab copy can produce the battle headlessly
with ``scripts/nova_selftest.sh <id>`` instead of a played one. A spec with a
``template:`` block needs no scenario there: its checks are generated from the
template's probes (``templates.harness_checks``), in the target's own move names,
so they always match the generated port. Other engines keep ``SCENARIOS``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ..appliers.essentials.dialect import detect_dialect
from ..appliers.essentials.resolution import build_resolution_map
from ..model import Ruleset
from ..model.schema import is_composed
from . import compose
from .harness_scenarios import SCENARIOS, SCENARIOS_ESSENTIALS21
from .templates import TemplateError, harness_checks

# One observation the plugin logged, e.g. "[chrooked:innerfocus] OBS move=FOCUSBLAST if=true result=ALWAYS_HIT".
_OBS_RE = re.compile(r"^\[chrooked:(?P<id>[^\]]+)\]\s+OBS\s+(?P<kv>.+)$")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RULESET_DIR = _REPO_ROOT / "ruleset"
_TARGETS_JSON = _REPO_ROOT / "targets.json"
_LOG_RELPATH = Path("Scripts") / "chrooked_load.log"
# Essentials 21: ports log to the game folder, and only while the marker exists at boot.
_V21_LOG_RELPATH = Path("chrooked_load.log")
ORACLE_MARKER = "chrooked-oracle.on"


def _is_v21(target: Path) -> bool:
    return detect_dialect(target) == "essentials21"


def log_path(target: Path) -> Path:
    """Where this target's ports write their OBS lines."""
    return target / (_V21_LOG_RELPATH if _is_v21(target) else _LOG_RELPATH)


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
    """True when every criterion key equals the observation's value (as strings).

    A list value accepts any of its entries, for a move whose internal name
    differs between engines (16.2's HIJUMPKICK is Essentials 21's HIGHJUMPKICK).
    """
    def ok(key: str, value: object) -> bool:
        seen = str(observation.get(key))
        if isinstance(value, (list, tuple)):
            return seen in {str(v) for v in value}
        return seen == str(value)
    return all(ok(key, value) for key, value in criteria.items())


def score(observations: list[dict[str, str]], checks: list[dict[str, object]],
          test_cases: tuple) -> list[dict[str, object]]:
    """Score each check against the observations; return per-case results.

    A case fails if no observation matches its ``select`` (the staged action was
    not seen) or if the matching observation violates ``expect``. A check marked
    ``absent`` (NV-25: a case the target game cannot have, such as a field effect in
    a game without fields) is neither: ``passed`` is None and ``reason`` says why.
    """
    results: list[dict[str, object]] = []
    for index, check in enumerate(checks):
        given = test_cases[index].given if index < len(test_cases) else f"case {index + 1}"
        if check.get("absent"):
            results.append({"passed": None, "given": given, "reason": f"not in this game: {check['absent']}"})
            continue
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


def _load_checks(mechanic_id: str, ruleset_dir: Path, target: Path) -> tuple[list[dict[str, object]], tuple]:
    """Return (checks, spec test_cases), failing loudly if they are out of sync.

    On an Essentials 21 target a templated spec's checks are generated from its
    probes, resolved against the target's PBS, and a hand port's come from
    SCENARIOS_ESSENTIALS21 when it has an entry there; everything else uses SCENARIOS.
    A composed ability (NV-15) is checked part by part (behavior.compose).
    """
    ruleset = Ruleset.load(ruleset_dir)
    spec = ruleset.behaviors.get(mechanic_id)
    v21 = _is_v21(target)
    if spec is not None and spec.template is not None and v21:
        try:
            return harness_checks(spec, build_resolution_map(target, ruleset)), spec.test_cases
        except TemplateError as error:
            raise SystemExit(f"cannot generate checks for '{mechanic_id}': {error}") from error
    ability = ruleset.abilities.get(mechanic_id)
    # A composed ability is scored part by part, also when it keeps a descriptive spec
    # of its own with no port (Solar Dynamo, NV-31), as the installer composes it then.
    unported_own = spec is None or (spec.template is None and mechanic_id not in SCENARIOS_ESSENTIALS21)
    if unported_own and ability is not None and is_composed(ability) and v21:
        try:
            return compose.harness_checks(ability, ruleset, build_resolution_map(target, ruleset))
        except (compose.CompositionError, TemplateError) as error:
            raise SystemExit(f"cannot generate checks for '{mechanic_id}': {error}") from error
    table = SCENARIOS_ESSENTIALS21 if v21 and mechanic_id in SCENARIOS_ESSENTIALS21 else SCENARIOS
    if mechanic_id not in table:
        raise SystemExit(f"no harness scenario for '{mechanic_id}' (add one in harness_scenarios.py)")
    if spec is None:
        raise SystemExit(f"no behavior spec '{mechanic_id}' in {ruleset_dir}/behaviors")
    checks = table[mechanic_id]
    if len(checks) != len(spec.test_cases):
        raise SystemExit(
            f"scenario for '{mechanic_id}' has {len(checks)} checks but the spec has "
            f"{len(spec.test_cases)} test_cases — keep them aligned 1:1.")
    return checks, spec.test_cases


def cmd_stage(mechanic_id: str, ruleset_dir: Path, target: Path) -> int:
    """Clear the log and print the in-game actions that produce this mechanic's observations."""
    checks, _ = _load_checks(mechanic_id, ruleset_dir, target)
    path = log_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")  # fresh session
    print(f"Staged '{mechanic_id}'. Log cleared: {path}")
    if _is_v21(target):
        (target / ORACLE_MARKER).write_text("harness\n")
        print(f"Oracle marker set: {target / ORACLE_MARKER} (ports log only while it exists at boot)")
        print(f"Lab copy: run scripts/nova_selftest.sh {mechanic_id} instead of playing.")
        print("Played copy: boot the game, battle with the ability's holder, then do IN ORDER:\n")
    else:
        print("Boot the game (debug), start a debug battle, then do IN ORDER:\n")
    for index, check in enumerate(checks, start=1):
        print(f"  {index}. {check.get('stage')}")
    print(f"\nThen quit and run:  python -m chrooked_pokedex.behavior.harness verify {mechanic_id}")
    return 0


def cmd_verify(mechanic_id: str, ruleset_dir: Path, target: Path) -> int:
    """Read the log and print PASS/FAIL per test_case; exit non-zero on any failure."""
    checks, test_cases = _load_checks(mechanic_id, ruleset_dir, target)
    path = log_path(target)
    if not path.exists():
        raise SystemExit(f"no log at {path} — run `stage` and play the battle first")
    results = score(parse_observations(path.read_text(), mechanic_id), checks, test_cases)
    passed = absent = 0
    for result in results:
        tag = {True: "PASS", False: "FAIL", None: "N/A "}[result["passed"]]  # type: ignore[index]
        line = f"{tag} {mechanic_id} :: {result['given']}"
        if not result["passed"]:
            line += f"  ({result['reason']})"
        print(line)
        passed += 1 if result["passed"] else 0
        absent += 1 if result["passed"] is None else 0
    print(f"\n{passed}/{len(results) - absent} passed" + (f", {absent} not in this game" if absent else ""))
    if _is_v21(target) and (target / ORACLE_MARKER).exists():
        print(f"Note: {target / ORACLE_MARKER} is still set; delete it so a played copy stops logging.")
    return 0 if passed + absent == len(results) else 1


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
