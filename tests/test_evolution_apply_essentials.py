"""Essentials: evolution Overrides rewrite the pre-evolution's `Evolution` lines.

Both engines store evolution forward, on the pre-evolution, and Essentials writes
one `Evolution = SPECIES,METHOD,PARAM` line per branch (Eevee has ten). The Ruleset
stores the backward pointer (`evolution.from`), so the applier groups every override
by its source species and replaces that source's whole set of `Evolution` lines at
once — the same whole-list replace the pokeemerald evolution tier and learnsets use,
which is what stops a branching pre-evolution from clobbering itself one line at a time.

A method the vocab cannot render, or a source/target the resmap cannot resolve, is
reported (blocked/partial), never guessed.
"""

from pathlib import Path

from chrooked_pokedex.appliers.essentials import pbs_edit
from chrooked_pokedex.appliers.essentials.evolution_apply import apply_evolutions
from chrooked_pokedex.appliers.essentials.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.report import ApplyReport

_POKEMON = """\
[EEVEE]
Name = Eevee
BaseStats = 55,55,50,55,45,65
Evolution = VAPOREON,Item,WATERSTONE

[VAPOREON]
Name = Vaporeon
BaseStats = 130,65,60,65,110,95

[JOLTEON]
Name = Jolteon
BaseStats = 65,65,60,130,110,95

[SLIGGOO]
Name = Sliggoo
BaseStats = 68,75,53,40,83,113
Evolution = GOODRA,Level,40

[GOODRA]
Name = Goodra
BaseStats = 90,100,70,80,110,150
"""


def _target(tmp_path: Path, body: str = _POKEMON) -> Path:
    target = tmp_path / "essentials"
    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    (pbs / "pokemon.txt").write_text(body, encoding="utf-8")
    return target


def _ruleset(tmp_path: Path, files: dict[str, str]) -> Ruleset:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    for name, content in files.items():
        (root / "species" / f"{name}.yaml").write_text(content, encoding="utf-8")
    return Ruleset.load(root)


def _evolutions(target: Path, header: str) -> list[str]:
    text = (target / "PBS" / "pokemon.txt").read_text(encoding="utf-8")
    span = pbs_edit.find_section(text, header)
    return pbs_edit.get_section_values(text[span[0]:span[1]], "Evolution")


def test_level_evolution_rewrites_pre_evolution(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "goodra": (
            "name: Goodra\nchrooked_id: goodra\naka: { essentials: GOODRA }\n"
            "evolution: { from: Sliggoo, method: { level: 50 } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()

    changed = apply_evolutions(target, ruleset, resmap, report)
    assert (target / "PBS" / "pokemon.txt") in changed
    assert _evolutions(target, "SLIGGOO") == ["GOODRA,Level,50"]
    assert report.counts()["applied"] == 1


def test_item_evolution_renders_internal_item(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "vaporeon": (
            "name: Vaporeon\nchrooked_id: vaporeon\naka: { essentials: VAPOREON }\n"
            "evolution: { from: Eevee, method: { item: Water Stone } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    apply_evolutions(target, ruleset, resmap, ApplyReport())
    assert _evolutions(target, "EEVEE") == ["VAPOREON,Item,WATERSTONE"]


def test_branching_evolution_keeps_all_targets(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "vaporeon": (
            "name: Vaporeon\nchrooked_id: vaporeon\naka: { essentials: VAPOREON }\n"
            "evolution: { from: Eevee, method: { item: Water Stone } }\n"
        ),
        "jolteon": (
            "name: Jolteon\nchrooked_id: jolteon\naka: { essentials: JOLTEON }\n"
            "evolution: { from: Eevee, method: { item: Thunder Stone } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    apply_evolutions(target, ruleset, resmap, ApplyReport())
    targets = {line.split(",")[0] for line in _evolutions(target, "EEVEE")}
    assert targets == {"VAPOREON", "JOLTEON"}  # both branches survive whole-list replace


def test_essentials_escape_hatch_method_round_trips(tmp_path):
    # A method with no neutral key is carried verbatim via an `essentials:` hint.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "espeon": (
            "name: Espeon\nchrooked_id: espeon\naka: { essentials: VAPOREON }\n"
            "evolution: { from: Eevee, method: { essentials: HappinessDay } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    apply_evolutions(target, ruleset, resmap, ApplyReport())
    assert _evolutions(target, "EEVEE") == ["VAPOREON,HappinessDay"]


def test_unrenderable_method_reported_partial_not_guessed(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "goodra": (
            "name: Goodra\nchrooked_id: goodra\naka: { essentials: GOODRA }\n"
            "evolution: { from: Sliggoo, method: { mystery: true } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()
    apply_evolutions(target, ruleset, resmap, report)
    entry = [e for e in report.entries if e.category == "evolution"][0]
    assert entry.status == "partial"
    assert _evolutions(target, "SLIGGOO") == ["GOODRA,Level,40"]  # left intact


def test_missing_pre_evolution_section_blocked(tmp_path):
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "goodra": (
            "name: Goodra\nchrooked_id: goodra\naka: { essentials: GOODRA }\n"
            "evolution: { from: Phantom, method: { level: 40 } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()
    apply_evolutions(target, ruleset, resmap, report)
    entry = [e for e in report.entries if e.category == "evolution"][0]
    assert entry.status == "blocked"


def test_second_run_is_no_churn_and_reports_nothing(tmp_path):
    # Idempotency contract: once applied, a re-run writes nothing AND adds no report
    # line, so an "applied" entry always means the file was actually modified.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "goodra": (
            "name: Goodra\nchrooked_id: goodra\naka: { essentials: GOODRA }\n"
            "evolution: { from: Sliggoo, method: { level: 50 } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    apply_evolutions(target, ruleset, resmap, ApplyReport())  # first run lands it
    after_first = (target / "PBS" / "pokemon.txt").read_text(encoding="utf-8")

    second_report = ApplyReport()
    changed = apply_evolutions(target, ruleset, resmap, second_report)
    assert changed == set()
    assert (target / "PBS" / "pokemon.txt").read_text(encoding="utf-8") == after_first
    assert second_report.entries == []  # nothing changed -> no report line


def test_vanilla_pre_evolution_resolves_by_derived_internal(tmp_path):
    # The pre-evolution (Sliggoo) is NOT its own Ruleset species; it must still resolve
    # by its name-derived INTERNAL (SLIGGOO), which the target section validates.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "goodra": (
            "name: Goodra\nchrooked_id: goodra\naka: { essentials: GOODRA }\n"
            "evolution: { from: Sliggoo, method: { level: 50 } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()
    apply_evolutions(target, ruleset, resmap, report)
    assert _evolutions(target, "SLIGGOO") == ["GOODRA,Level,50"]
    assert report.counts()["applied"] == 1


def test_branch_with_unresolved_target_marks_source_partial(tmp_path):
    # Eevee has one resolvable branch (Vaporeon) and one whose evolved species symbol
    # cannot resolve. The source's whole-set entry must read partial, not applied.
    target = _target(tmp_path)
    ruleset = _ruleset(tmp_path, {
        "vaporeon": (
            "name: Vaporeon\nchrooked_id: vaporeon\naka: { essentials: VAPOREON }\n"
            "evolution: { from: Eevee, method: { item: Water Stone } }\n"
        ),
        # No aka and a name that derives to an internal absent from the target, so the
        # evolved symbol resolves but the species genuinely is a phantom branch.
        "ghostmon": (
            "name: Ghostmon\nchrooked_id: ghostmon\n"
            "evolution: { from: Eevee, method: { item: Thunder Stone } }\n"
        ),
    })
    resmap = build_resolution_map(target, ruleset)
    # Force the phantom branch's target to be unresolvable.
    resmap.species_by_id.pop("ghostmon", None)
    report = ApplyReport()
    apply_evolutions(target, ruleset, resmap, report)
    source_entry = [e for e in report.entries
                    if e.category == "evolution" and e.symbol == "EEVEE"][0]
    assert source_entry.status == "partial"
    # The resolvable branch still landed.
    assert "VAPOREON,Item,WATERSTONE" in _evolutions(target, "EEVEE")


def test_no_evolution_override_no_entry_no_churn(tmp_path):
    target = _target(tmp_path)
    before = (target / "PBS" / "pokemon.txt").read_text(encoding="utf-8")
    ruleset = _ruleset(tmp_path, {
        "goodra": "name: Goodra\nchrooked_id: goodra\naka: { essentials: GOODRA }\n",
    })
    resmap = build_resolution_map(target, ruleset)
    report = ApplyReport()
    changed = apply_evolutions(target, ruleset, resmap, report)
    assert changed == set()
    assert (target / "PBS" / "pokemon.txt").read_text(encoding="utf-8") == before
    assert report.entries == []
