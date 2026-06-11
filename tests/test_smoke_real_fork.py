"""Smoke test: the vendored readers still parse a real pokeemerald fork.

These tests run only when the Dreamstone fork is present at the expected
sibling path. They prove the readers survived vendoring and parse real C,
not just hand-written fixtures. Skipped (not failed) when the fork is absent,
so CI on a clean checkout stays green.
"""

from pathlib import Path

import pytest

from chrooked_pokedex.readers.pokeemerald.species_parser import parse_species_profiles

_DREAMSTONE = Path(
    "/Users/cdbrooks/Development/Games/ROMs/dreamstone-mysteries"
)

_have_fork = (_DREAMSTONE / "src" / "data" / "pokemon").exists()
skip_no_fork = pytest.mark.skipif(
    not _have_fork, reason="Dreamstone fork not present at sibling path"
)


@skip_no_fork
def test_species_parser_reads_dreamstone_goodra() -> None:
    profiles = parse_species_profiles(_DREAMSTONE)
    assert profiles, "expected a non-empty species table from the real fork"
    assert "SPECIES_GOODRA" in profiles
