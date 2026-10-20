"""Per-Target Mod selection: which static mods a Target turns off.

A Mod is a self-contained script file an Applier installs into a Target outside
the Ruleset data (Rejuv: ``references/rejuv-harness/chrooked_zz_<id>.rb``). Every
Mod installs by default; a Target opts out by id in
``ruleset/targets/<slug>/mods.yaml``, committed canon:

    off:
      - kirinprobe

Storing the OFF list (not an on list) keeps an absent file meaning "install
everything" — the behavior before selection existed — and lets a newly written
Mod reach every Target without a second edit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import yaml

_FILE = "mods.yaml"


def mods_path(ruleset_dir: Path, slug: str) -> Path:
    return Path(ruleset_dir) / "targets" / slug / _FILE


def load_mods_off(ruleset_dir: Path, slug: Optional[str]) -> frozenset[str]:
    """The Mod ids turned off for ``slug``; empty when no slug or no file."""
    if not slug:
        return frozenset()
    path = mods_path(ruleset_dir, slug)
    if not path.exists():
        return frozenset()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    off = data.get("off", []) if isinstance(data, dict) else None
    if not isinstance(off, list) or not all(isinstance(i, str) for i in off):
        raise ValueError(f"{path}: 'off' must be a list of mod ids")
    return frozenset(off)


def write_mods_off(ruleset_dir: Path, slug: str, off: Iterable[str]) -> Path:
    """Write the off list (sorted, so a re-save leaves git clean)."""
    path = mods_path(ruleset_dir, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Static mods turned off for this Target. Every mod not listed installs.\n"
        "# Edited from the dex Mods tab; apply removes a listed mod's file.\n"
    )
    body = yaml.safe_dump({"off": sorted(set(off))}, sort_keys=False)
    path.write_text(header + body, encoding="utf-8")
    return path
