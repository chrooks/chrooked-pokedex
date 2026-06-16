"""The Essentials 16.2 (Africanvs-era) dialect.

A clean fork of the I/O + resolution layers for the older PBS format: numeric `[N]`
section headers with identity in an `InternalName=` field (pokemon.txt, types.txt),
flat positional CSV for moves.txt / abilities.txt, a per-file BOM (pokemon.txt has
none), and CRLF line endings throughout. Resolution keys off INTERNAL names, never the
Spanish display `Name`.

This package owns only byte-faithful read/write and resolution. The neutral model,
Apply Report, and behavior packet are imported from the shared modules untouched. Tier
appliers (species / moves / type-chart) and items.txt land in later issues (#21–#24).
"""
