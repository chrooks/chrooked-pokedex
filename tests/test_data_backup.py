"""The shared Essentials Data/ backup — the boot-recompile brick net."""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials import data_backup
from chrooked_pokedex.appliers.essentials.data_backup import (
    DataBackupError,
    backup_essentials_data,
)


@pytest.mark.unit
def test_creates_backup_when_absent(tmp_path: Path) -> None:
    fork = tmp_path / "game"
    (fork / "Data").mkdir(parents=True)
    (fork / "Data" / "core.dat").write_text("ORIGINAL", encoding="utf-8")

    result = backup_essentials_data(fork)

    assert result["status"] == "created"
    assert (fork / "Data.bak" / "core.dat").read_text(encoding="utf-8") == "ORIGINAL"


@pytest.mark.unit
def test_keeps_existing_backup_unclobbered(tmp_path: Path) -> None:
    """A second backup must never overwrite a good Data.bak with a bricked Data/."""
    fork = tmp_path / "game"
    (fork / "Data").mkdir(parents=True)
    (fork / "Data" / "core.dat").write_text("BRICKED", encoding="utf-8")
    (fork / "Data.bak").mkdir()
    (fork / "Data.bak" / "core.dat").write_text("GOOD", encoding="utf-8")

    result = backup_essentials_data(fork)

    assert result["status"] == "kept"
    assert (fork / "Data.bak" / "core.dat").read_text(encoding="utf-8") == "GOOD"


@pytest.mark.unit
def test_skips_when_no_data_dir(tmp_path: Path) -> None:
    fork = tmp_path / "game"
    fork.mkdir()

    result = backup_essentials_data(fork)

    assert result["status"] == "skipped"
    assert not (fork / "Data.bak").exists()


@pytest.mark.unit
def test_failed_copy_raises_and_drops_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fork = tmp_path / "game"
    (fork / "Data").mkdir(parents=True)
    (fork / "Data" / "core.dat").write_text("x", encoding="utf-8")

    def _boom(src, dst):  # noqa: ANN001
        Path(dst).mkdir()  # leave a partial backup behind
        raise OSError("disk full")

    monkeypatch.setattr(data_backup.shutil, "copytree", _boom)

    with pytest.raises(DataBackupError):
        backup_essentials_data(fork)
    # the partial Data.bak must be cleaned up, not left to mask the next backup
    assert not (fork / "Data.bak").exists()
