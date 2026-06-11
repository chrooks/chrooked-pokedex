---
name: port-behavior
description: Port a Ruleset behavior spec (a custom Pokémon ability/move mechanic) into a target pokeemerald-expansion or Pokémon Essentials fork. Use when implementing a custom mechanic into an engine, porting a behavior, or filling the reference library. Checks references/ for a cached patch first (deterministic git apply); on a cache miss it emits the implementation packet, spawns a behavior-port agent, compiles, verifies against the spec's acceptance tests, and captures the new patch.
argument-hint: "<mechanic-id> [--engine pokeemerald] [--target PATH]"
disable-model-invocation: true
---

# Port Behavior

Implement one Ruleset **behavior spec** into a real engine fork. This is the LLM-as-compiler
[Surface](~/.claude/CONTEXT.md) — kept deliberately apart from the deterministic data applier
(`chrooked-pokedex apply`), which must stay pure and reproducible. The LLM's output is a
*proposal* that only becomes trusted after it compiles, passes review against the spec's
acceptance tests, and you approve it. Determinism is recovered at the **reference library**:
once a patch is captured, future ports of that exact (mechanic, engine, version) are a plain
`git apply`, no LLM.

## Quick start

```
/port-behavior innerfocus --engine pokeemerald --target ../ROMs/pokeemerald-expansion
```

- `<mechanic-id>` (required) — the behavior spec's `chrooked_id` (a file in `ruleset/behaviors/`).
- `--engine` (default `pokeemerald`) — which engine hint to surface; `pokeemerald` or `essentials`.
- `--target` (required for a cache miss) — path to the fork to edit. Must be git-clean.

## Algorithm: cache-first

1. **Resolve the spec.** Confirm `ruleset/behaviors/<mechanic-id>.yaml` loads:
   `chrooked-pokedex behaviors --mechanic <id>` (errors if unknown).
2. **Read the target version.** From `<target>/include/constants/expansion.h`
   (`EXPANSION_VERSION_MAJOR/MINOR/PATCH`) build `<engine>-<major.minor.patch>`, e.g.
   `pokeemerald-expansion-1.15.3`. For Essentials, use the game's version string.
3. **Cache check.** If `references/<mechanic-id>.<engine>-<version>.patch` exists → **cache hit**.
   Else → **cache miss**.

### Cache hit (no LLM)

```
git -C <target> apply --check references/<id>.<engine>-<version>.patch   # verify it still applies
git -C <target> apply        references/<id>.<engine>-<version>.patch
```

If `--check` fails (the engine drifted), treat it as a cache miss and re-derive; flag that the
stored patch is stale.

### Cache miss (invoke the LLM)

1. **Confirm the target is git-clean.** `git -C <target> status --porcelain` — abort if there are
   tracked changes (you need a clean diff to capture). Untracked files are fine.
2. **Emit the packet.**
   `chrooked-pokedex behaviors --mechanic <id> --engine <engine>` — this is the self-contained brief.
3. **Spawn a behavior-port subagent** (Task/Agent tool) with the packet. Use the prompt template
   below. The subagent gets ONLY the packet — that is the test of spec sufficiency.
4. **Static-verify** the returned diff yourself:
   - the gate matches the spec (right condition, right ownership — attacker vs target ability);
   - it does not leak (other moves / other abilities unaffected);
   - it did not duplicate vanilla logic;
   - it touched only the intended file(s) and carries the `// chrooked:<id>` tag.
   - Walk EACH acceptance test in the spec and argue why the edit satisfies it.
5. **Compile** (best effort). For pokeemerald-expansion, in Docker:
   ```bash
   docker run --rm -v "$(cd <target> && pwd)":/project -w /project \
     devkitpro/devkitarm:20240202 \
     bash -c "apt-get update -qq >/dev/null && apt-get install -y -qq build-essential libpng-dev libelf-dev >/dev/null; make modern -j$(sysctl -n hw.ncpu); echo MAKE_EXIT=\${PIPESTATUS[0]}"
   ```
   (gcc 13.2 image — see the project memory `pokeemerald-build-toolchain`. Newer expansions may
   accept a newer image.) A clean `make` proves it *builds*; it does NOT prove the runtime
   behavior — say so honestly.
6. **Capture** the patch BEFORE cleanup:
   `git -C <target> diff > references/<id>.<engine>-<version>.patch`
   and add/update the row in `references/README.md`.
7. **Restore the target** (it is usually a keeper): `git -C <target> checkout -- <edited files>`,
   remove build artifacts (`pokeemerald.gba`, `pokeemerald.elf`, `pokeemerald.map`, `build/`).
8. **Surface for review.** Show the diff, the chosen [Seam](~/.claude/CONTEXT.md), the compile
   result, and the per-acceptance-test argument. **Do not commit until the human approves** — this
   is the highest-stakes step (a subtly-wrong mechanic poisons playtesting silently).

## Subagent prompt template

> You are a behavior-port implementer. Implement ONE custom Pokémon battle mechanic into the fork
> at `<target>` (engine `<engine>`, version `<version>`), working ONLY from the spec packet below.
> Read the engine to find the idiomatic Seam — do not blindly copy any reference; a newer engine
> may centralize this differently.
>
> [paste the full packet here]
>
> Tasks: explore the relevant source; verify any vanilla part of the mechanic already exists and do
> not duplicate it; implement the custom part with a minimal, well-commented edit tagged
> `// chrooked:<id>`; gate it exactly as the spec says (mind attacker-vs-target ownership). DO NOT
> compile and DO NOT edit other files. Return: the function/Seam + file:line, the unified diff
> (`git -C <target> diff`), and a short argument for EACH acceptance test (especially that the
> effect does not leak to other moves or users).

## Honest limits

- **Runtime acceptance tests are not auto-run.** Compile + static review is the current gate. The
  spec's `given/expect` cases are verified by reasoning, not execution. Closing that hole (a battle
  harness or a manual playtest checklist) is separate work.
- **Essentials path** reuses the same flow with the `essentials` engine hint, but has no Docker
  compile step — lean harder on review.
