"""The Rejuv save reader: Marshal bytes -> caught Rejuv dex ids."""

from __future__ import annotations

import pytest

from chrooked_pokedex.web import rejuv_save

pytestmark = pytest.mark.unit


def _long(n: int) -> bytes:
    assert 0 <= n < 123  # enough for a fixture
    return bytes([n + 5]) if n else b"\x00"


def _sym(name: str) -> bytes:
    return b":" + _long(len(name)) + name.encode()


def _str(s: str) -> bytes:
    return b'I"' + _long(len(s)) + s.encode() + _long(1) + _sym("E") + b"T"


def _hash(pairs: list[tuple[bytes, bytes]]) -> bytes:
    return b"{" + _long(len(pairs)) + b"".join(k + v for k, v in pairs)


def _obj(cls: str, ivars: list[tuple[str, bytes]]) -> bytes:
    return b"o" + _sym(cls) + _long(len(ivars)) + b"".join(_sym(k) + v for k, v in ivars)


def _entry(forms: list[tuple[str, int]]) -> bytes:
    return _obj(
        "PokedexListEntry",
        [("@forms", _hash([(_str(f), _hash([(_sym("owned"), b"i" + _long(n))])) for f, n in forms]))],
    )


def _save() -> bytes:
    dex_list = _hash(
        [
            (_sym("GOODRA"), _entry([("Normal Form", 1), ("Hisuian Form", 0)])),
            (_sym("DEERLING"), _entry([("Spring Form", 0), ("Autumn Form", 2)])),
            (_sym("BULBASAUR"), _entry([("Normal Form", 0)])),
        ]
    )
    pokedex = _obj("Pokedex", [("@dexList", dex_list)])
    return b"\x04\x08" + _hash([(_sym("Trainer"), _obj("PokeBattle_Trainer", [("@pokedex", pokedex)]))])


def test_caught_ids_join_rejuv_dex_ids() -> None:
    # Base form -> bare slug; any other form -> slug--formslug (snapshot_rejuv's ids).
    assert rejuv_save.caught_ids(rejuv_save.load(_save())) == ["deerling--autumnform", "goodra"]


def test_read_caught_uses_newest_save_and_skips_conflicts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SAVES_DIR", str(tmp_path))
    (tmp_path / "Game.rxdata").write_bytes(_save())
    assert rejuv_save.read_caught()["caught"] == ["deerling--autumnform", "goodra"]

    (tmp_path / "Game.sync-conflict-20260101-000000-ABCDEFG.rxdata").write_bytes(b"junk")
    assert rejuv_save.read_caught()["available"] is True


def test_unreadable_save_degrades_instead_of_raising(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SAVES_DIR", str(tmp_path))
    (tmp_path / "Game.rxdata").write_bytes(b"not marshal")
    assert rejuv_save.read_caught()["available"] is False
