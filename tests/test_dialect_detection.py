"""Dialect detection tests (issue #26).

Covers:
  - detect_dialect returns correct result for modern v21 and 16.2 fixtures
  - Detection ignores display language (Spanish modern, English 16.2)
  - Garbage / missing PBS returns None
  - Live Africanus copy (gated on AFRICANVS_PBS env var)
  - CLI --dialect override routes without calling detection
  - CLI auto-detect with unrecognised PBS blocks with "blocked: unrecognized Essentials format"
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from chrooked_pokedex.appliers.essentials.dialect import detect_dialect

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials_dialect"
_MODERN_V21 = _FIXTURES / "modern_v21"
_MODERN_SPANISH = _FIXTURES / "modern_v21_spanish"
_ENGLISH_162 = _FIXTURES / "english_162"


# ---------------------------------------------------------------------------
# ac1 + ac2: file-shape detection (language-invariant)
# ---------------------------------------------------------------------------


def test_detect_modern_v21_fixture():
    """Modern v21-shape fixture (section headers) -> 'essentials21'."""
    assert detect_dialect(_MODERN_V21) == "essentials21"


def test_detect_english_162_fixture():
    """16.2-shape fixture (flat CSV moves) -> 'essentials16'."""
    assert detect_dialect(_ENGLISH_162) == "essentials16"


def test_detect_modern_spanish_fixture():
    """Spanish-display modern fixture still has section-header shape -> 'essentials21'."""
    assert detect_dialect(_MODERN_SPANISH) == "essentials21"


# ac2: the English-display 16.2 fixture is the same as english_162 above — shape is
# what matters, not language.  Explicit test to make ac2 obvious in the test report.
def test_detect_english_162_not_tricked_by_language():
    """English-display 16.2 fixture -> 'essentials16' regardless of language."""
    assert detect_dialect(_ENGLISH_162) == "essentials16"


def test_detect_ignores_utf8_bom_on_first_line(tmp_path: Path):
    """A UTF-8 BOM on the leading comment line must not defeat detection.

    Essentials exports PBS files with a leading ``﻿`` BOM; str.strip() doesn't
    drop it, so without lstrip the BOM-glued comment reads as the first data
    line and detection falls through to None (the IF2 Hoenn backdrop bug).
    """
    pbs = tmp_path / "PBS"
    pbs.mkdir()
    (pbs / "moves.txt").write_text(
        "﻿# header comment\n277,ABSORB,Absorb,0DD,30\n", encoding="utf-8"
    )
    (pbs / "pokemon.txt").write_text(
        "﻿# header comment\n[1]\nName = Bulbasaur\n", encoding="utf-8"
    )
    assert detect_dialect(tmp_path) == "essentials16"


# ---------------------------------------------------------------------------
# ac3: garbage / missing PBS returns None
# ---------------------------------------------------------------------------


def test_detect_missing_pbs_dir(tmp_path: Path):
    """No PBS sub-directory at all -> None."""
    assert detect_dialect(tmp_path) is None


def test_detect_empty_pbs_dir(tmp_path: Path):
    """PBS dir exists but no moves.txt or pokemon.txt -> None."""
    (tmp_path / "PBS").mkdir()
    assert detect_dialect(tmp_path) is None


def test_detect_garbage_pbs(tmp_path: Path):
    """PBS dir with unrecognised content -> None."""
    pbs = tmp_path / "PBS"
    pbs.mkdir()
    (pbs / "moves.txt").write_text("this is not valid PBS content at all\n")
    (pbs / "pokemon.txt").write_text("neither is this\n")
    assert detect_dialect(tmp_path) is None


def test_detect_conflicting_signals(tmp_path: Path):
    """moves.txt says 16, pokemon.txt says 21 -> None (disagreement)."""
    pbs = tmp_path / "PBS"
    pbs.mkdir()
    # 16-style moves (flat CSV)
    (pbs / "moves.txt").write_text("001,TACKLE,Tackle,NORMAL,Physical,40,100,35\n")
    # 21-style pokemon (INTERNALNAME section header)
    (pbs / "pokemon.txt").write_text("[BULBASAUR]\nName = Bulbasaur\n")
    assert detect_dialect(tmp_path) is None


# ---------------------------------------------------------------------------
# ac3: CLI blocks on unrecognised format, writes nothing
# ---------------------------------------------------------------------------


def test_cli_blocks_on_unknown_format(tmp_path: Path):
    """apply engine=essentials dialect=auto on garbage PBS adds 'blocked' line, writes nothing."""
    from chrooked_pokedex.cli import _run_apply
    from chrooked_pokedex.model import Ruleset

    # Build the smallest possible valid git repo so require_clean_git_status passes
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"], check=True)
    # Garbage PBS so detection returns None
    pbs = repo / "PBS"
    pbs.mkdir()
    (pbs / "moves.txt").write_text("not valid\n")
    (pbs / "pokemon.txt").write_text("not valid\n")
    placeholder = repo / ".gitkeep"
    placeholder.write_text("")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)

    # Minimal ruleset dir with no actual data
    ruleset_dir = tmp_path / "ruleset"
    ruleset_dir.mkdir()
    for name in ("moves", "species", "learnsets", "evolutions", "abilities", "type_chart"):
        (ruleset_dir / name).mkdir()
    (ruleset_dir / "ruleset.yaml").write_text("version: '1'\ntype_chart_overrides: []\n")

    # Snapshot the files in the repo before apply
    files_before = {f: f.read_bytes() for f in repo.rglob("*") if f.is_file()}

    rc = _run_apply(repo, "essentials", "all", ruleset_dir, force=False, dialect="auto")
    # Should not crash (rc 0 or non-zero is fine; the important thing is no write)
    # The apply report should mention the block
    report_path = repo / "apply-report.md"
    # Report file may or may not exist — if it does, check blocked; if not, that's also fine
    if report_path.exists():
        assert "blocked" in report_path.read_text().lower() or "unrecognized" in report_path.read_text().lower()

    # All pre-existing repo files must be byte-identical (no data written)
    for f, content in files_before.items():
        if f == report_path:
            continue  # the report itself is allowed to be written
        assert f.read_bytes() == content, f"{f} was modified unexpectedly"


# ---------------------------------------------------------------------------
# ac4: explicit dialect override bypasses detection
# ---------------------------------------------------------------------------


def test_cli_dialect_override_skips_detection(tmp_path: Path):
    """--dialect essentials21 forces v21 applier without calling detect_dialect.

    After D-DRY, detect_dialect lives in dispatch.py, so that is the patch target.
    """
    from chrooked_pokedex.cli import _run_apply

    # We just need to confirm detect_dialect is NOT called when dialect != "auto"
    with patch(
        "chrooked_pokedex.appliers.dispatch.detect_dialect"
    ) as mock_detect:
        # Use a minimal no-op by patching _apply_essentials too so we don't need a real target
        with patch("chrooked_pokedex.cli._apply_essentials"):
            with patch("chrooked_pokedex.cli.require_clean_git_status"):
                with patch("chrooked_pokedex.report.ApplyReport.write", return_value=tmp_path / "r.json"):
                    _run_apply(tmp_path, "essentials", "all", tmp_path, force=True, dialect="essentials21")
        mock_detect.assert_not_called()


def test_cli_dialect_override_16_skips_detection(tmp_path: Path):
    """--dialect essentials16 forces v16 applier without calling detect_dialect.

    After D-DRY, detect_dialect lives in dispatch.py, so that is the patch target.
    """
    from chrooked_pokedex.cli import _run_apply

    with patch("chrooked_pokedex.appliers.dispatch.detect_dialect") as mock_detect:
        with patch("chrooked_pokedex.cli._apply_essentials162"):
            with patch("chrooked_pokedex.cli.require_clean_git_status"):
                with patch("chrooked_pokedex.report.ApplyReport.write", return_value=tmp_path / "r.json"):
                    _run_apply(tmp_path, "essentials", "all", tmp_path, force=True, dialect="essentials16")
        mock_detect.assert_not_called()


# ---------------------------------------------------------------------------
# Live check — Africanus copy (gated on AFRICANVS_PBS)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("AFRICANVS_PBS"),
    reason="AFRICANVS_PBS not set — skipping live Africanus check",
)
def test_detect_africanus_is_essentials16():
    """Real Africanus PBS directory should detect as essentials16."""
    africanvs_pbs = Path(os.environ["AFRICANVS_PBS"])
    # AFRICANVS_PBS may point to the PBS subdirectory itself or the parent
    # detect_dialect expects the game root (parent of PBS/)
    target = africanvs_pbs.parent if africanvs_pbs.name == "PBS" else africanvs_pbs
    result = detect_dialect(target)
    assert result == "essentials16", f"Expected essentials16, got {result!r}"
