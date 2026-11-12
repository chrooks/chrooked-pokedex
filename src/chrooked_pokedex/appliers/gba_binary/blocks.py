"""The Blocks file: CRC-checked byte replacements the emulator applies in memory.

Format 1 (the Contract with the PokeDaisy fork, ADR 0003): blocks sorted by
address, no timestamp, so an unchanged Ruleset rewrites a byte-identical file.
"""

from __future__ import annotations

import json
import os
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BLOCKS_FILE = "chrooked.blocks.json"


@dataclass(frozen=True)
class Block:
    address: int        # GBA ROM bus address (0x08000000 + file offset)
    original: bytes     # what the ROM holds there today (CRC'd for the loader)
    patched: bytes      # the full replacement, same length


def render_blocks(rom_sha1: str, blocks: Iterable[Block]) -> str:
    body = {
        "format": 1,
        "rom_sha1": rom_sha1,
        "blocks": [
            {
                "address": f"0x{b.address:08X}",
                "length": len(b.patched),
                "original_crc32": f"0x{zlib.crc32(b.original):08X}",
                "bytes": b.patched.hex(),
            }
            for b in sorted(blocks, key=lambda b: b.address)
        ],
    }
    return json.dumps(body, indent=2) + "\n"


def write_blocks_file(target: Path, rom_sha1: str, blocks: Iterable[Block]) -> Path:
    """Write atomically (temp file in the same folder, then rename)."""
    path = Path(target) / BLOCKS_FILE
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".blocks-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(render_blocks(rom_sha1, blocks))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path
