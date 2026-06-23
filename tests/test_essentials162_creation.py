"""Creation-path tests for the Essentials 16.2 species applier (#60 Bucket C).

A species the target genuinely lacks (no `[N]` section anywhere) is CREATED by merging
the full base data from the `.base/<version>.json` seed snapshot with the Ruleset
Override, then emitting a complete `[N]` section. The Override alone is a diff and
rarely carries types + a full six-stat block; the snapshot supplies the rest.

A species with neither a target section NOR base snapshot data still blocks — nothing
is fabricated from thin air. An ability that does not resolve in the target's
abilities.txt is omitted and the species reported partial (never a dangling reference).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from chrooked_pokedex.appliers.essentials162 import pbs_io, resolution, species_apply
from chrooked_pokedex.model.schema import AbilitiesOverride, SpeciesOverride
from chrooked_pokedex.report import ApplyReport

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"

# Abilities present in the fixture abilities.txt (so they resolve).
_DRIZZLE = "Drizzle"
_STENCH = "Stench"

_BASE_FULL = {
    "types": ["Water"],
    "stats": {"hp": 50, "atk": 60, "def": 70, "spe": 80, "spa": 90, "spd": 100},
    "abilities": {"primary": _DRIZZLE, "secondary": None, "hidden": None},
}


class _Ruleset:
    def __init__(self, species=None, base_species=None):
        self.species = species or {}
        self.base_species = base_species or {}


def _target(tmp_path: Path) -> Path:
    pbs = tmp_path / "PBS"
    pbs.mkdir()
    for name in ("pokemon.txt", "types.txt", "abilities.txt", "moves.txt"):
        shutil.copy(_FIXTURES / name, pbs / name)
    return tmp_path


def _apply(target: Path, ruleset):
    resmap = resolution.build_resolution_map(target, ruleset)
    report = ApplyReport()
    species_apply.apply_species(target, ruleset, resmap, report)
    text, _ = pbs_io.read(target / "PBS" / "pokemon.txt")
    return text, report


def _section(text: str, internal: str) -> str:
    marker = f"InternalName={internal}"
    start = text.index(marker)
    head = text.rfind("[", 0, start)
    nxt = text.find("\n[", start)
    return text[head: nxt if nxt != -1 else len(text)]


def test_creates_absent_species_by_merging_base_snapshot(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(
        species={
            "testmon": SpeciesOverride(
                name="Testmon", chrooked_id="testmon",
                abilities=AbilitiesOverride(secondary=_STENCH),
            ),
        },
        base_species={"testmon": _BASE_FULL},
    )
    text, report = _apply(target, ruleset)

    section = _section(text, "TESTMON")
    assert "Name=Testmon" in section
    assert "Type1=WATER" in section
    assert "BaseStats=50,60,70,80,90,100" in section          # _STAT_ORDER: hp,atk,def,spe,spa,spd
    assert "Abilities=DRIZZLE,STENCH" in section              # base primary + override secondary
    assert any(
        e.chrooked_id == "testmon" and e.status == "applied" for e in report.entries
    )


def test_override_stat_layers_over_base_stat(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(
        species={
            "testmon": SpeciesOverride(
                name="Testmon", chrooked_id="testmon", stats={"atk": 5},
            ),
        },
        base_species={"testmon": _BASE_FULL},
    )
    text, _ = _apply(target, ruleset)
    section = _section(text, "TESTMON")
    assert "BaseStats=50,5,70,80,90,100" in section  # Atk overridden, rest from base


def test_unresolved_ability_is_omitted_and_reported_partial(tmp_path):
    target = _target(tmp_path)
    base = dict(_BASE_FULL)
    base["abilities"] = {"primary": "Permafrost", "secondary": None, "hidden": None}
    ruleset = _Ruleset(
        species={
            "testmon": SpeciesOverride(name="Testmon", chrooked_id="testmon"),
        },
        base_species={"testmon": base},
    )
    text, report = _apply(target, ruleset)
    section = _section(text, "TESTMON")
    assert "Permafrost" not in section          # custom ability, not in target -> omitted
    assert "Abilities=" not in section          # nothing resolved, no dangling line
    entry = next(e for e in report.entries if e.chrooked_id == "testmon")
    assert entry.status == "partial"


def test_absent_species_without_base_data_still_blocks(tmp_path):
    target = _target(tmp_path)
    ruleset = _Ruleset(
        species={
            "ghostmon": SpeciesOverride(
                name="Ghostmon", chrooked_id="ghostmon",
                abilities=AbilitiesOverride(primary=_DRIZZLE),
            ),
        },
        base_species={},  # no snapshot data
    )
    text, report = _apply(target, ruleset)
    assert "InternalName=GHOSTMON" not in text
    entry = next(e for e in report.entries if e.chrooked_id == "ghostmon")
    assert entry.status == "blocked"


def test_incomplete_base_stats_block_reason_names_the_gap(tmp_path):
    # A base snapshot missing some stats must NOT silently blame the Override — the
    # blocked reason names the missing stat keys so it is diagnosable.
    target = _target(tmp_path)
    partial_base = {"types": ["Water"], "stats": {"hp": 50, "atk": 60}, "abilities": {}}
    ruleset = _Ruleset(
        species={"testmon": SpeciesOverride(name="Testmon", chrooked_id="testmon")},
        base_species={"testmon": partial_base},
    )
    _, report = _apply(target, ruleset)
    entry = next(e for e in report.entries if e.chrooked_id == "testmon")
    assert entry.status == "blocked"
    assert "stats:" in entry.reason
    assert "def" in entry.reason and "spe" in entry.reason
