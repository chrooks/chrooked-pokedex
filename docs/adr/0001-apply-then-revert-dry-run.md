# Apply-then-revert as the dry-run engine

The frontend needs a no-write preview that classifies every Ruleset entry as applied / partial / blocked / created — and it must match what a real apply does, byte for byte. Rather than maintain a second model-layer reimplementation of the appliers (which would silently drift) or copy each Target fork to a temp dir per preview (slow, disk-heavy), the preview runs the **real Appliers** on the Target, captures the Apply Report, and then restores the Target with `git checkout . && git clean -fd`. This is safe because `apply` already requires a clean git working tree on the Target, so the revert returns it to a known-good state exactly.

## Considered Options

- **Apply-then-revert via git** (chosen) — faithful by construction; the preview *is* apply. Reuses 100% of existing applier code, no new write paths.
- **Apply to a temp copy** — copy the Target minus `.git` to a temp dir, apply there, discard. Never mutates the real Target, but copying a whole pokeemerald fork per preview is slow and disk-heavy.
- **Model-layer diff (no appliers)** — reimplement merge + classify at the model layer. Fast and would also power the canon dex, but a second code path that can diverge from real applier behavior (gated `#if` branches, the tiered create step) without any test catching it.

## Consequences

- A future reader will see *preview* mutate the game on disk then restore it, and wonder why — this ADR is the answer: fidelity over surprise-avoidance.
- Preview inherits apply's **clean-tree requirement**. A dirty Target cannot be previewed; the UI must show an Error State ("commit or stash this game first") instead.
- The revert must include `git clean -fd` so the `apply-report.md` the report writer drops into the Target is swept along with the tracked-file changes.
- Previews on the same Target must be serialized — two concurrent apply-then-revert runs would corrupt each other's restore.
- If a preview is interrupted (crash, kill) mid-run, the Target is left mutated; recovery is the same `git checkout . && git clean -fd`. The UI should run this guard on Target re-selection.
