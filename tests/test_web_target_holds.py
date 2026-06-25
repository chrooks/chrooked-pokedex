"""The web apply/preview path loads per-Target holds + edits by namespace slug."""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.web.targets import Target, _load_target_layers


def _target(namespace=None) -> Target:
    return Target(
        id="abc", label="Africanvs", path="/games/africanvs",
        engine="essentials", namespace=namespace,
    )


def _write_layers(ruleset_dir: Path, slug: str) -> None:
    d = ruleset_dir / "targets" / slug
    d.mkdir(parents=True)
    (d / "holds.yaml").write_text(
        "holds:\n  - id: gothita\n    categories: [species, learnset]\n",
        encoding="utf-8",
    )
    (d / "edits.yaml").write_text(
        "learnset_add:\n  - id: gothita\n    moves:\n      - { level: 1, move: Water Whip }\n",
        encoding="utf-8",
    )


@pytest.mark.unit
def test_loads_layers_by_namespace(tmp_path: Path) -> None:
    _write_layers(tmp_path, "africanvs")
    holds, edits = _load_target_layers(tmp_path, _target(namespace="africanvs"))
    assert holds.is_held("gothita", "learnset")
    assert edits.learnset_additions("gothita")


@pytest.mark.unit
def test_no_ruleset_dir_yields_empty(tmp_path: Path) -> None:
    _write_layers(tmp_path, "africanvs")
    holds, edits = _load_target_layers(None, _target(namespace="africanvs"))
    assert not holds.is_held("gothita", "learnset")
    assert not edits.learnset_additions("gothita")


@pytest.mark.unit
def test_no_namespace_yields_empty(tmp_path: Path) -> None:
    _write_layers(tmp_path, "africanvs")
    holds, edits = _load_target_layers(tmp_path, _target(namespace=None))
    assert not holds.is_held("gothita", "learnset")
    assert not edits.learnset_additions("gothita")


@pytest.mark.unit
def test_unsupported_engine_blocks_not_silently(tmp_path: Path) -> None:
    """Holds set for a non-essentials16 engine produce a blocked note, never a silent skip."""
    from chrooked_pokedex.appliers.dispatch import _warn_unsupported_target_layers
    from chrooked_pokedex.model.holds import HoldSet
    from chrooked_pokedex.model.target_edits import TargetEdits
    from chrooked_pokedex.report import ApplyReport

    report = ApplyReport()
    holds = HoldSet(held={"gothita": frozenset({"learnset"})})
    _warn_unsupported_target_layers(holds, TargetEdits(), "pokeemerald", report)
    assert report.counts()["blocked"] == 1
    assert "not yet honored" in report.entries[0].reason

    # Empty holds → no note (unsupported engines stay quiet when nothing is held).
    quiet = ApplyReport()
    _warn_unsupported_target_layers(HoldSet(), TargetEdits(), "pokeemerald", quiet)
    assert quiet.counts()["blocked"] == 0
