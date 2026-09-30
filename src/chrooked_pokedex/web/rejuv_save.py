"""Caught species from a Rejuvenation save.

Syncthing already mirrors every device's saves folder onto hestia (see
``save_sync``), so the newest ``*.rxdata`` there *is* the latest save — no
upload step. A save is a Ruby ``Marshal.dump`` of a hash; ``:Trainer`` carries
``@pokedex.@dexList``: species symbol -> ``PokedexListEntry`` whose ``@forms``
maps a form name to ``{owned: count, ...}``. The first form is the base form.

Ids follow ``snapshot_rejuv``: base form = ``slug(SPECIES)``, any other form =
``slug(SPECIES)--slug(form name)``, so they join the Rejuv backdrop dex as-is.
"""

from __future__ import annotations

import logging
import os
import struct
from pathlib import Path
from typing import Any

from ..seed.neutralize import slug
from .save_sync import DEFAULT_SAVES_DIR

_logger = logging.getLogger(__name__)


class RubyObject:
    """A Marshal'd object of any class: its class name and ``@ivars``."""

    def __init__(self, cls: str) -> None:
        self.cls = cls
        self.ivars: dict[str, Any] = {}


class _Reader:
    """Minimal Ruby Marshal 4.8 reader — enough for an RGSS save.

    ponytail: user-dumped blobs (Table, Color, Tone) come back as raw bytes;
    decode them only if a feature ever needs one.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 2  # skip the \x04\x08 version header
        self.symbols: list[str] = []
        self.objects: list[Any] = []

    def byte(self) -> int:
        b = self.data[self.pos]
        self.pos += 1
        return b

    def raw(self, n: int) -> bytes:
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def long(self) -> int:
        c = struct.unpack("b", bytes([self.byte()]))[0]
        if c == 0:
            return 0
        if 5 < c < 128:
            return c - 5
        if -129 < c < -5:
            return c + 5
        n = 0
        for i in range(abs(c)):
            n |= self.byte() << (8 * i)
        return n if c > 0 else n - (1 << (8 * -c))

    def bytestr(self) -> bytes:
        return self.raw(self.long())

    def sym(self) -> str:
        return self.read()  # a symbol slot is always ':' or ';'

    def keep(self, obj: Any) -> Any:
        self.objects.append(obj)
        return obj

    def read(self) -> Any:  # noqa: C901 — one branch per Marshal type byte
        t = chr(self.byte())
        if t == "0":
            return None
        if t == "T":
            return True
        if t == "F":
            return False
        if t == "i":
            return self.long()
        if t == ":":
            s = self.bytestr().decode("utf-8", "replace")
            self.symbols.append(s)
            return s
        if t == ";":
            return self.symbols[self.long()]
        if t == "@":
            return self.objects[self.long()]
        if t == "I":  # wrapped value + ivars (string encoding)
            obj = self.read()
            for _ in range(self.long()):
                self.sym()
                self.read()
            return obj
        if t == '"':
            return self.keep(self.bytestr().decode("utf-8", "replace"))
        if t == "f":
            s = self.bytestr().decode()
            return self.keep(float({"inf": "inf", "-inf": "-inf", "nan": "nan"}.get(s, s)))
        if t == "l":
            sign = self.byte()
            n = int.from_bytes(self.raw(self.long() * 2), "little")
            return self.keep(n if sign == ord("+") else -n)
        if t == "[":
            arr: list[Any] = self.keep([])
            arr.extend(self.read() for _ in range(self.long()))
            return arr
        if t in "{}":
            h: dict[Any, Any] = self.keep({})
            for _ in range(self.long()):
                k = self.read()
                h[k if isinstance(k, (str, int, float, bool, type(None))) else id(k)] = self.read()
            if t == "}":
                self.read()  # default value
            return h
        if t in "oS":
            obj = self.keep(RubyObject(self.sym()))
            for _ in range(self.long()):
                name = self.sym()
                obj.ivars[name] = self.read()
            return obj
        if t == "u":
            self.sym()
            return self.keep(self.bytestr())
        if t == "U":
            obj = self.keep(RubyObject(self.sym()))
            obj.ivars["marshal_load"] = self.read()
            return obj
        if t == "e":
            self.sym()
            return self.read()
        if t in "cmM":
            return self.keep(self.bytestr().decode())
        if t == "/":
            src = self.keep(self.bytestr().decode("utf-8", "replace"))
            self.byte()
            return src
        if t == "C":
            self.sym()
            return self.read()
        if t == "d":
            self.sym()
            return self.keep(self.read())
        raise ValueError(f"unsupported Marshal type {t!r} at byte {self.pos - 1}")


def load(data: bytes) -> Any:
    if data[:2] != b"\x04\x08":
        raise ValueError("not a Ruby Marshal 4.8 file")
    return _Reader(data).read()


def caught_ids(save: Any) -> list[str]:
    """Rejuv backdrop dex ids for every species/form the save has owned."""
    dex = save["Trainer"].ivars["@pokedex"].ivars["@dexList"]
    ids = []
    for species, entry in dex.items():
        for i, (form, info) in enumerate(entry.ivars["@forms"].items()):
            if info.get("owned", 0):
                base = slug(species)
                ids.append(base if i == 0 else f"{base}--{slug(form)}")
    return sorted(ids)


def newest_save(saves_dir: Path) -> Path | None:
    saves = [p for p in saves_dir.glob("*.rxdata") if ".sync-conflict-" not in p.name]
    return max(saves, key=lambda p: p.stat().st_mtime, default=None)


def read_caught() -> dict[str, Any]:
    """``{available, save, saved_at, caught}`` — degrades like ``save_sync``."""
    saves_dir = Path(os.environ.get("SAVES_DIR", DEFAULT_SAVES_DIR))
    path = newest_save(saves_dir) if saves_dir.is_dir() else None
    if path is None:
        return {"available": False, "caught": []}
    try:
        caught = caught_ids(load(path.read_bytes()))
    except (ValueError, KeyError, IndexError, AttributeError) as error:
        # A half-synced or foreign save must not 500 the dex; log why instead.
        _logger.warning("unreadable Rejuv save %s: %s", path.name, error)
        return {"available": False, "caught": [], "error": f"{path.name}: {error}"}
    return {
        "available": True,
        "save": path.name,
        "saved_at": path.stat().st_mtime,
        "caught": caught,
    }
