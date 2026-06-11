"""Refuse to write into a target with a dirty git working tree.

Writing into a dirty tree would make it impossible to tell the applier's changes
apart from the user's own uncommitted edits. The guard is bypassable with
`force=True` for throwaway targets.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class DirtyWorkingTree(RuntimeError):
    pass


def require_clean_git_status(target: Path, force: bool = False) -> None:
    if force:
        return
    result = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Not a git repo (or git unavailable): nothing to protect, allow.
        return
    if result.stdout.strip():
        raise DirtyWorkingTree(
            f"target {target} has uncommitted changes; commit/stash them or pass "
            "--force to apply anyway."
        )
