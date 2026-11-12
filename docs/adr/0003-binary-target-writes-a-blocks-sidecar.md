# A binary Target gets a Blocks file beside the ROM, not a patched ROM

Pokémon Monomyth is a closed pokeemerald ROM hack: there is no source tree, only a 32 MB `.gba` file, and every existing Applier edits text files in a folder. We still want the Ruleset to reach it. The `gba-binary` Applier treats the ROM as the read-only baseline: for each matched species it reads the record from the ROM, changes only the overridden fields, and writes the result as a **Blocks file** (`chrooked.blocks.json`) beside the ROM — a sorted list of `{address, length, original_crc32, bytes}` entries. PokeDaisy's fork loads that file into emulator memory at boot, so the ROM file never changes and the app still recognizes the game by its hash. The fork owns *where the tables are* (its generator emits the **Addresses file**, `monomyth.addresses.json`, carrying the ROM's sha1, species names, type names, and each table's address, stride, and field offsets); the dex owns *what the bytes should be*. The Blocks file is the whole Contract between the two repos, frozen at format 1.

## Considered Options

- **Blocks file of CRC-checked records** (chosen) — the ROM stays untouched, the emulator applies the blocks in memory, and each block carries the CRC32 of the bytes it expects to replace, so a ROM update or a stale file fails loud instead of corrupting a table. Neither repo needs the other's code.
- **`.bps` patch of the ROM** — rejected: a patched ROM has a new hash, which breaks the app's game detection, and the patch hides which fields changed.
- **Generated Kotlin tables in the fork** — rejected: couples the two repos at build time; every Ruleset change would need a fork rebuild.
- **A copy of the ROM on hestia** — rejected: it drifts from the copy actually played, and ROM bytes must never land in git. Apply runs on the machine that holds the ROM.

## Consequences

- No apply-then-revert dry run (ADR 0001) is needed for this engine: the ROM is never written, so the Blocks file is the only artifact to revert.
- The dex never derives an address. Field offsets come from the Addresses file; a missing or malformed file, or one whose `rom_sha1` does not match the `.gba` beside it, aborts the apply before any block is written.
- A CRC mismatch at load time is a loud refusal on the fork side, never a silent partial write.
- Species match the Ruleset by exact display name once, confirmed by Chris via `match --write`, and are stored as `aka: { monomyth: <index> }`. A miss is a `blocked` report row; the dex overwrites only species the ROM already has and never creates one.
- The Blocks file has no timestamp and is sorted by address, so an unchanged Ruleset rewrites it byte-identical.
- This engine is CLI-only until a ROM snapshot reader exists for the dex UI backdrop and web registry (issue #134).
