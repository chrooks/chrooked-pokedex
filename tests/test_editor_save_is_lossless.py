"""The editor save must not silently delete anything.

A save REGENERATES the file from a frozen dataclass — it is not an in-place
edit. So the file can only keep what the dataclass, the serializer, the write
allowlist and the writer ALL know about. Every one of those is a place a field
can quietly disappear, and each has done so:

  second_type   serialize_move omitted it, so Muddy Water lost its Ground half
  header notes  nothing modelled comments, so 332 lines across 115 files died

These tests are the identity case: loading a record and saving it back unchanged
must leave both its data and its header comments intact.
"""
from __future__ import annotations

import dataclasses
import glob
from pathlib import Path

import pytest

from chrooked_pokedex.model import loader
from chrooked_pokedex.seed import writer
from chrooked_pokedex.web import collections as colmod
from chrooked_pokedex.web import crud

pytestmark = pytest.mark.unit

KINDS = {
    "moves": (loader.load_move, colmod.serialize_move, writer.move_yaml,
              crud._move_from_payload, crud._MOVE_FIELDS, loader._MOVE_KEYS),
    "abilities": (loader.load_ability, colmod.serialize_ability, writer.ability_yaml,
                  crud._ability_from_payload, crud._ABILITY_FIELDS, loader._ABILITY_KEYS),
    "species": (loader.load_species, crud.serialize_species, writer.species_yaml,
                crud._species_from_payload, crud._SPECIES_FIELDS, loader._SPECIES_KEYS),
    "behaviors": (loader.load_behavior, colmod.serialize_behavior, writer.behavior_yaml,
                  crud._behavior_from_payload, crud._BEHAVIOR_FIELDS, loader._BEHAVIOR_KEYS),
}


def _identity_save(kind: str, path: Path, tmp: Path) -> object:
    """Round-trip one file through the exact path a UI save takes.

    The write goes through crud._validated_write — the real chokepoint — rather
    than reimplementing it, so this also guards the WIRING. Testing the helper
    directly passed even with the helper unwired from the writer.
    """
    load, serialize, write, from_payload, _fields, _keys = KINDS[kind]
    stored = load(path)
    merged = crud._merge_over_stored(dict(serialize(stored)), path, load, serialize)
    # _validated_write reads the header off the file it is about to replace, so
    # the original has to be sitting at the destination — exactly as in the app.
    tmp.write_text(path.read_text("utf-8"), encoding="utf-8")
    crud._validated_write(tmp, write(from_payload(merged, stored.chrooked_id)), load)
    return stored, load(tmp), tmp.read_text("utf-8")


def _norm(value: object) -> object:
    """Compare ignoring trailing scalar whitespace.

    A YAML folded block (``effect: >``) keeps a trailing newline that a quoted
    scalar does not, so a faithful round-trip still differs by that one
    character. That is formatting, not data — normalise it away, recursively,
    so real loss inside nested effects/test_cases is still caught.
    """
    if isinstance(value, str):
        return value.strip()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(_norm(getattr(value, f.name)) for f in dataclasses.fields(value))
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_norm(v) for v in value)
    return value


def _same(a: object, b: object) -> bool:
    return _norm(a) == _norm(b)


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_write_allowlist_and_serializer_cover_every_stored_field(kind: str) -> None:
    """Three independent allowlists must agree, or a save rejects or deletes."""
    load, serialize, _w, _f, fields, keys = KINDS[kind]
    files = sorted(glob.glob(f"ruleset/{kind}/*.yaml"))
    assert files, f"no {kind} to check"
    served = set(serialize(load(Path(files[0]))))
    assert not set(keys) - set(fields), (
        f"{kind}: loader stores fields the write allowlist rejects: "
        f"{sorted(set(keys) - set(fields))}")
    assert not set(keys) - served, (
        f"{kind}: serializer drops stored fields, so every save DELETES them: "
        f"{sorted(set(keys) - served)}")


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_identity_save_preserves_all_data(kind: str, tmp_path: Path) -> None:
    tmp = tmp_path / "rt.yaml"
    broken: list[str] = []
    for path in sorted(glob.glob(f"ruleset/{kind}/*.yaml")):
        before, after, _text = _identity_save(kind, Path(path), tmp)
        for f in dataclasses.fields(before):
            x, y = getattr(before, f.name), getattr(after, f.name)
            if x != y and not _same(x, y):
                broken.append(f"{Path(path).name}:{f.name}")
    assert not broken, f"saving unchanged loses data: {broken[:10]}"


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_identity_save_preserves_header_comments(kind: str, tmp_path: Path) -> None:
    """The authored header block is the design record; a save must not eat it."""
    tmp = tmp_path / "rt.yaml"
    broken: list[str] = []
    for path in sorted(glob.glob(f"ruleset/{kind}/*.yaml")):
        p = Path(path)
        header = crud._leading_comments(p.read_text("utf-8"))
        if not header.strip():
            continue
        _b, _a, text = _identity_save(kind, p, tmp)
        for line in (l.strip() for l in header.splitlines() if l.strip()):
            if line not in text:
                broken.append(f"{p.name}: {line[:50]}")
                break
    assert not broken, f"saving unchanged eats header comments: {broken[:10]}"
