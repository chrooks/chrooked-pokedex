"""The behavior-port side of the Ruleset.

The data applier writes engine data deterministically. This package handles the other
half of the Boundary: turning a human-owned BehaviorSpec into a portable, self-contained
brief (a "packet") that a context-aware implementer compiles into a specific engine, plus
a manifest of every mechanic the target must carry.
"""

from .packet import render_manifest, render_packet

__all__ = ["render_manifest", "render_packet"]
