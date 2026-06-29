# ExecPlan — Cache the merged dex (#59) + apply-preview reports (#63)

> Status: ready to implement. All design decisions resolved (see Decision Ledger).
> Issues: [#59 Cache the merged dex by ruleset version](https://github.com/chrooks/chrooked-pokedex/issues/59),
> [#63 Cache apply reports, keyed on ruleset + target fingerprint](https://github.com/chrooks/chrooked-pokedex/issues/63).

## Goal

Stop recomputing two deterministic, read-heavy results when their inputs have not
changed:

- **#59** — `GET /api/dex` re-merges a ~2.9 MB base snapshot with the Ruleset
  overrides on every request. Cache the merged dex, keyed on the Ruleset content.
- **#63** — the apply **preview** (apply-then-revert) re-runs the whole Applier
  every time, even when the Ruleset and the Target files are byte-identical to the
  last preview. Cache the preview report, keyed on Ruleset + Target content. Also
  serve the last real apply's on-disk report for cheap re-display.

Both ride the same lesson: **a content-fingerprinted cache key makes invalidation
automatic** — a changed input is simply a new key, old entries fall out, and a
stale result can never be served. No manual cache-busting.

## Why one plan

Both halves need the same missing primitive: a **Ruleset fingerprint**. `meta.yaml`
has no per-edit version field (only `base_version`, `schema_version`), so the
"version" must be derived from content. #59 keys on `(base_version, rs_fp)`; #63
keys on `(rs_fp, tgt_fp)`. Build the fingerprint once, consume it twice.

## Decision Ledger (resolved in grill)

| # | Decision | Choice |
|---|----------|--------|
| Q1 | What #63 caches | Preview report cache + serve the on-disk apply sidecar for re-display. Real apply stays an uncached one-shot write (it mutates the Target and the clean-tree gate blocks re-apply, so a `(rs, tgt)` key would never hit on re-apply). |
| Q2 | Ruleset fingerprint (shared) | sha256 over the bytes of every file under `ruleset/` (sorted rel-paths). Standalone function — computable **without** a full `Ruleset.load`, so a cache check can skip the load. |
| Q3 | Target fingerprint (#63) | sha256 over the engine's input file set: `PBS/*.txt` for essentials (exactly what `_snapshot_pbs_files` already globs); for pokeemerald, hash the parsed `build_snapshot` dict as a pragmatic stand-in (see Risks). |
| Q4 | Preview cache home (#63) | In-process on `TargetState`, single slot per Target path: `dict[path] -> (key, report_payload)`. New key overwrites; old falls out free. Serialized on the existing per-fork lock. |
| Q5 | Dex cache (#59) | Module/app-level single slot, fp-gated via the standalone hash, scoped to `GET /api/dex` only. Hit returns the cached merged dex, skipping load **and** merge. Other `build_dex` call sites stay uncached (YAGNI). |
| Q6 | Proof (both) | Hit/miss counter asserted in tests (deterministic; no timing flake). Doubles as the issues' "hit/miss log" learning artifact. |

## New primitive

`src/chrooked_pokedex/fingerprint.py` (new, small):

```python
import hashlib
from pathlib import Path

def hash_files(paths: list[Path], root: Path) -> str:
    """sha256 over sorted (rel-path, bytes) pairs. Order-stable, content-exact."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(root)).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()

def hash_ruleset_dir(ruleset_dir: Path) -> str:
    files = [p for p in ruleset_dir.rglob("*") if p.is_file()]
    return hash_files(files, ruleset_dir)
```

`# ponytail:` stdlib hashlib, no new dep. Reads every ruleset file each call —
cheaper than the merge/applier it gates, and unavoidable without a version field.

## Slice 1 — #59 dex cache (AFK)

**Reuses:** `web/dex.py::build_dex`, `web/app.py::get_dex` (≈ line 125,
`_load_snapshot_or_503()` + `build_dex(snapshot, _load_ruleset_or_503())`), the
pinned `base_version` (1.11.2).
**Adds:** the fingerprint primitive + one single-slot cache.

Flow for `GET /api/dex`:

```
rs_fp = hash_ruleset_dir(RULESET_DIR)        # cheap file read, NO parse
key   = (base_version, rs_fp)
if _dex_cache.key == key:                     # HIT
    _dex_cache.hits += 1
    return _dex_cache.dex                      # skip load + 2.9MB merge
# MISS
_dex_cache.misses += 1
dex = build_dex(_load_snapshot_or_503(), _load_ruleset_or_503())
_dex_cache = Slot(key, dex, ...)
return dex
```

- Single-slot holder (module-level or `app.state`), guarded by one
  `threading.Lock` (`# ponytail:` global lock, fine for a single-process app —
  per-key locks only if a hot path needs them).
- `hits`/`misses` counters exposed for the test.

**Steps**
1. Add `fingerprint.py` + a unit test (`hash_ruleset_dir` changes iff a file's
   bytes change; stable across reads).
2. Add the single-slot cache + counters; wire into `get_dex`.
3. Tests: first `GET /api/dex` → miss+compute; second → hit, `build_dex` not
   re-invoked (spy/monkeypatch); edit a `ruleset/` file → next call misses and
   serves the new merge.

**Acceptance criteria**
- [ ] Merged dex reused across requests when `ruleset/` content is unchanged.
- [ ] Key includes `base_version` + `rs_fp`; editing a ruleset file yields a fresh
      merge automatically (no manual invalidation call).
- [ ] A hit skips `build_dex` (proven: `build_dex` invocation count == 1 across two
      identical requests).
- [ ] Editing the ruleset serves the updated dex on the next read (never stale).
- [ ] Hit/miss counter asserted: `misses==1, hits==1` over two identical requests.

## Slice 2 — #63 preview cache + serve last apply report (AFK)

**Reuses:** `web/targets.py::TargetState` (per-fork `lock_for`, `_snapshots`,
`invalidate_snapshot`), `preview_target`, `_run_applier` → `appliers/dispatch.py::route_apply`,
`_report_payload`, `_snapshot_pbs_files` (PBS glob), `report.write` (writes
`apply-report.md` + `.json` sidecar via `with_suffix`).
**Adds:** a per-Target preview slot keyed on `(rs_fp, tgt_fp)` + a tiny "read the
sidecar" path.

Preview flow (inside the existing per-fork lock in `preview_target`):

```
key = (rs_fp, tgt_fp(target))                 # rs_fp shared with Slice 1
slot = state._preview.get(target.path)
if slot and slot.key == key:                  # HIT
    return slot.payload                        # skip applier + restore churn
# MISS: existing snapshot -> run applier -> restore (unchanged)
payload = _report_payload(report)
state._preview[target.path] = Slot(key, payload)
return payload
```

- `tgt_fp(target)`: essentials → `hash_files(PBS/*.txt)`; pokeemerald →
  `hash` of the parsed `build_snapshot` dict (Risks).
- Single slot per Target path on `TargetState` (`dict[path] -> Slot`), under the
  existing `lock_for(path)`. Real `apply_target` already calls
  `invalidate_snapshot`; have it drop the preview slot too (apply changed the
  Target, so the old preview is stale by definition).
- **Serve last apply report:** the JSON sidecar (`<target>/apply-report.json`) is
  already written on every real apply. Re-display = read that file. `# ponytail:`
  no cache object needed — the file *is* the cache.

**Steps**
1. Add `tgt_fp` helper (engine-routed) + `_preview` slot on `TargetState`.
2. Gate `preview_target` on the slot; store on miss; clear on `apply_target`.
3. Tests: two identical previews → applier runs once (spy on `route_apply`); edit
   ruleset OR a target PBS file → next preview misses; real apply clears the slot.

**Acceptance criteria**
- [ ] Preview report reused when both `rs_fp` and `tgt_fp` are unchanged.
- [ ] Key includes `rs_fp` AND `tgt_fp`; a change to either yields a fresh report
      automatically (no manual invalidation).
- [ ] A hit skips re-running the Applier (proven: `route_apply` count == 1 across
      two identical previews).
- [ ] Editing the ruleset or the target files serves a freshly computed report on
      the next preview (never stale).
- [ ] A real apply invalidates the preview slot for that Target.
- [ ] Hit/miss counter asserted (`misses==1, hits==1` over two identical previews).

## File map

| File | Change |
|------|--------|
| `src/chrooked_pokedex/fingerprint.py` | **new** — `hash_files`, `hash_ruleset_dir` |
| `src/chrooked_pokedex/web/app.py` | dex single-slot cache + counters; wire into `get_dex` |
| `src/chrooked_pokedex/web/targets.py` | `tgt_fp` helper; `_preview` slot on `TargetState`; gate `preview_target`; clear slot in `apply_target` |
| `tests/test_fingerprint.py` | **new** — fingerprint stability/change |
| `tests/test_web_dex.py` | dex hit/miss + staleness |
| `tests/test_web_targets.py` | preview hit/miss + invalidation-on-apply |

## Risks / notes

- **pokeemerald `tgt_fp`.** Hashing the parsed `build_snapshot` dict is correct
  only if the Applier reads nothing outside what the snapshot parses. Acceptable:
  essentials (IF2) is the live target and uses the exact PBS glob; pokeemerald is
  the dev's own tree. `# ponytail:` no C-file enumerator until pokeemerald preview
  caching actually matters.
- **Fingerprint cost.** `hash_ruleset_dir` reads all ruleset files per `GET
  /api/dex`. Cheaper than the merge it skips; revisit only if profiling says so.
- **Thread-safety.** Single-slot dict mutation under one lock per cache. No
  eviction policy needed — single slot is the eviction.

## Out of scope

- Caching real apply to "skip the Applier" (Q1: apply mutates + is gated).
- Caching the other `build_dex` call sites (per-Target backdrops) — different
  inputs, more keys; not what #59 asks.
- On-disk/persistent cache — both caches are in-process; the web process is
  long-lived and the apply sidecar already persists.
