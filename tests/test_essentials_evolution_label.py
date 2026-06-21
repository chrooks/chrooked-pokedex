"""#39 — unit coverage for the Essentials-local evolution method labeler."""

from __future__ import annotations

import pytest

from chrooked_pokedex.web.essentials_evolution import essentials_method_label


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method", "param", "expected"),
    [
        ("Level", "16", "Level 16"),
        ("Item", "WATERSTONE", "Water Stone"),
        ("Item", "THUNDERSTONE", "Thunder Stone"),
        ("HappinessDay", "0", "Happiness Day"),
        ("Trade", "0", "Trade"),
        ("Trade", "", "Trade"),
        ("HasMove", "ANCIENTPOWER", "Has Move Ancientpower"),
        ("LevelMale", "20", "Level Male 20"),
    ],
)
def test_label_branches(method: str, param: str, expected: str) -> None:
    assert essentials_method_label(method, param) == expected


@pytest.mark.unit
def test_no_raw_token_leaks() -> None:
    """An unmodeled method token is humanized, never echoed raw."""
    label = essentials_method_label("SomeNovelMethod", "0")
    assert "_" not in label
    assert label == "Some Novel Method"
