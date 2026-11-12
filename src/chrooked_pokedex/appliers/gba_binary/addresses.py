"""Load the Addresses file and check it belongs to the ROM beside it."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ADDRESSES_FILE = "monomyth.addresses.json"
# GBA cartridge ROM is mapped at this bus address; file offset = address - base.
ROM_BUS_BASE = 0x08000000


class AddressesError(ValueError):
    """The Addresses file is missing, malformed, or belongs to another ROM."""


@dataclass(frozen=True)
class Table:
    address: int
    stride: int
    fields: Mapping[str, int]


@dataclass(frozen=True)
class Addresses:
    rom_sha1: str
    species_names: tuple[str, ...]
    types: tuple[str, ...]
    tables: Mapping[str, Table]


def _table(name: str, raw: Mapping[str, Any]) -> Table:
    try:
        return Table(
            address=int(str(raw["address"]), 0),
            stride=int(raw["stride"]),
            fields={str(k): int(v) for k, v in raw["fields"].items()},
        )
    except (KeyError, TypeError, ValueError) as error:
        raise AddressesError(f"{ADDRESSES_FILE}: table '{name}' is malformed ({error}).") from error


def load_addresses(target: Path) -> Addresses:
    path = Path(target) / ADDRESSES_FILE
    if not path.is_file():
        raise AddressesError(
            f"{ADDRESSES_FILE} not found in {target}; copy the fork's generated "
            "Addresses file into the Target folder."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AddressesError(f"{ADDRESSES_FILE}: not valid JSON ({error}).") from error
    tables = data.get("tables") or {}
    if "base_stats" not in tables:
        raise AddressesError(f"{ADDRESSES_FILE}: missing required table 'base_stats'.")
    try:
        return Addresses(
            rom_sha1=str(data["rom_sha1"]).lower(),
            species_names=tuple(str(n) for n in data["species_names"]),
            types=tuple(str(t) for t in data["types"]),
            tables={name: _table(name, raw) for name, raw in tables.items()},
        )
    except KeyError as error:
        raise AddressesError(f"{ADDRESSES_FILE}: missing key {error}.") from error


def find_rom(target: Path) -> Path:
    roms = sorted(Path(target).glob("*.gba"))
    if len(roms) != 1:
        raise AddressesError(
            f"expected exactly one .gba file in {target}, found {len(roms)}."
        )
    return roms[0]


def verify_rom(target: Path, addresses: Addresses) -> Path:
    """Return the ROM path; raise when its SHA1 differs from the Addresses file's."""
    rom = find_rom(target)
    with rom.open("rb") as handle:
        actual = hashlib.file_digest(handle, "sha1").hexdigest()
    if actual != addresses.rom_sha1:
        raise AddressesError(
            f"{rom.name} sha1 {actual} does not match {ADDRESSES_FILE} rom_sha1 "
            f"{addresses.rom_sha1}; regenerate the Addresses file for this ROM."
        )
    return rom
