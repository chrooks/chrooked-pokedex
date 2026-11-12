"""Applier for closed GBA ROM builds (first Target: Pokémon Monomyth 1.1).

Apply-only, CLI-only. The ROM is never written: the Applier reads each matched
species record from the ROM, overlays the Ruleset's Overrides, and writes the
result as CRC-checked blocks into a Blocks file (`chrooked.blocks.json`) that
the emulator applies in memory. Table locations come from the fork's Addresses
file (`monomyth.addresses.json`); the dex never derives an address. See ADR 0003.
"""
