"""`match --engine gba-binary`: propose Monomyth matches, --write stores aka hints."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from chrooked_pokedex.cli import main

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"
HEADER = "# Bulbasaur: probe species for the Monomyth slice."


@pytest.fixture
def ruleset_dir(tmp_path):
    rs = tmp_path / "ruleset"
    shutil.copytree(FIXTURES / "sample_ruleset", rs)
    (rs / "species" / "bulbasaur.yaml").write_text(
        f"{HEADER}\n"
        "name: Bulbasaur\n"
        "chrooked_id: bulbasaur\n"
        "aka: { dex: 1 }\n"
        "types: [Grass, Poison]\n"
        "stats: { hp: 60 }\n",
        encoding="utf-8",
    )
    return rs


def _match(ruleset_dir: Path, *extra: str) -> int:
    return main([
        "match", "--engine", "gba-binary",
        "--target", str(FIXTURES / "gba_binary"),
        "--ruleset", str(ruleset_dir), *extra,
    ])


def test_prints_one_row_per_species(ruleset_dir, capsys):
    assert _match(ruleset_dir) == 0
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith(("bulbasaur", "goodra"))]
    assert len(rows) == 2
    bulba = next(r for r in rows if r.startswith("bulbasaur"))
    goodra = next(r for r in rows if r.startswith("goodra"))
    assert "#1 Bulbasaur" in bulba
    assert "(no match)" in goodra


def test_dry_run_writes_nothing(ruleset_dir):
    before = (ruleset_dir / "species" / "bulbasaur.yaml").read_text()
    _match(ruleset_dir)
    assert (ruleset_dir / "species" / "bulbasaur.yaml").read_text() == before


def test_write_stores_hint_and_keeps_header(ruleset_dir, capsys):
    assert _match(ruleset_dir, "--write") == 0
    text = (ruleset_dir / "species" / "bulbasaur.yaml").read_text()
    assert text.splitlines()[0] == HEADER
    data = yaml.safe_load(text)
    assert data["aka"] == {"dex": 1, "monomyth": 1}
    assert data["types"] == ["Grass", "Poison"]
    assert data["stats"] == {"hp": 60}
    # The unmatched species is untouched.
    assert "monomyth" not in (ruleset_dir / "species" / "goodra.yaml").read_text()
    # Second run sees the hint and writes nothing new.
    capsys.readouterr()
    _match(ruleset_dir, "--write")
    assert "wrote 0 hint(s)" in capsys.readouterr().out
