"""Milestone 0 — the `snapshot` and `ui` CLI subcommands."""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.cli import main

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE = _REPO_ROOT.parent / "ROMs" / "_scratch-expansion-1.11.2"


def test_ui_errors_cleanly_when_snapshot_missing(tmp_path: Path, capsys) -> None:
    code = main(["ui", "--snapshot", str(tmp_path / "absent.json")])
    assert code == 1
    assert "base snapshot not found" in capsys.readouterr().err


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_snapshot_subcommand_is_idempotent(tmp_path: Path) -> None:
    out = tmp_path / "1.11.2.json"
    assert main(["snapshot", "--base", str(_BASE), "--out", str(out)]) == 0
    first = out.read_bytes()
    assert main(["snapshot", "--base", str(_BASE), "--out", str(out)]) == 0
    assert out.read_bytes() == first  # byte-identical second run
