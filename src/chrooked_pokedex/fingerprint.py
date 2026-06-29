"""Content fingerprints for the read-caches (#59 dex, #63 apply preview).

A fingerprint is a sha256 over file *contents*, so it changes iff the bytes
change and is stable across reads — unlike mtime, which lies on checkout/touch.
Folding it into a cache key makes invalidation automatic: a changed input is a
new key, old entries fall out, and a stale result can never be served.

These functions deliberately do not parse anything: a cache check must be able to
compute the key *without* a full `Ruleset.load`, so a hit can skip the load.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_files(paths: list[Path], root: Path) -> str:
    """sha256 over the (relative-path, bytes) of each file, sorted for stability.

    Including the relative path means a rename changes the hash; the NUL
    separator keeps path/content boundaries unambiguous.
    """
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def hash_ruleset_dir(ruleset_dir: Path) -> str:
    """Fingerprint every hand-editable file under ``ruleset_dir`` (recursively).

    Dot-paths are skipped: it drops editor swap/`.DS_Store` noise (which would
    cause spurious cache misses), and crucially excludes the 2.9 MB
    ``.base/<version>.json`` snapshot — that input's identity is keyed separately
    by the caller, so re-reading it on every fingerprint is pure waste.
    """
    ruleset_dir = Path(ruleset_dir)
    files = [
        p
        for p in ruleset_dir.rglob("*")
        if p.is_file()
        and not any(part.startswith(".") for part in p.relative_to(ruleset_dir).parts)
    ]
    return hash_files(files, ruleset_dir)
