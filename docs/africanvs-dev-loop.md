# Africanvs dev loop (macOS / Apple Silicon)

The documented edit → see-it-in-game loop for projecting the Ruleset into Pokémon
Africanvs (Essentials 16.2) and verifying it.

## The one rule that took a day to learn

**Run the game under Wine `Game.exe`, never the native `Z-universal` binary.**

- Wine `Game.exe` bundles **Ruby 1.8**, which the Essentials 16.2 scripts require
  (they use 1.8 syntax like `when 0:`).
- The native `Z-universal.app` binary uses **modern Ruby (1.9+)**, which rejects
  that syntax and crashes on `048:AudioUtilities` before the title screen. Dead end
  for this (unported) game.

And **launch from Finder / `open`, not a raw terminal** — plus in debug mode set
`MKXPZ_WINDOWS_CONSOLE=0`, or the debug console window steals keyboard focus under
Wine. (Running `wine Game.exe debug` straight from a shell = dead keyboard.)

## Launchers (in the game copy)

Double-click in Finder, or `open` them:

| Launcher | Use |
|---|---|
| `Play Copy (Wine).command` | Plain play. No `$DEBUG`, no console. |
| `Play Copy (Wine Debug).command` | Dev loop: `$DEBUG` on (recompile + Debug menu), `MKXPZ_WINDOWS_CONSOLE=0` so keyboard works. |

Both `cd` into the copy and run `wine Game.exe`. The copy has **no root
`mkxp.json`** (matches the working original; under Wine real `kernel32`/`user32`
exist, so the macOS-only `my_win32_wrapper.rb` is not needed).

## The short path

```bash
scripts/africanvs_devloop.sh        # apply Ruleset, then open the debug launcher
scripts/africanvs_devloop.sh --apply-only   # just write PBS
scripts/africanvs_devloop.sh --no-apply     # just launch
```

`apply --engine essentials` auto-detects the 16.2 dialect (see #26). Tier data
appliers are #21+; until then apply is a foundation no-op, so to exercise the loop
**hand-edit a PBS value** to stand in for applier output.

## Tier 1 — PBS recompiles to Data/*.dat

Essentials rebuilds `Data/*.dat` from `PBS/*.txt` at boot when `$DEBUG` is set and a
PBS file is newer than its `.dat`. You see a compile screen for a few seconds.

- **Force a recompile** if mtime doesn't trip it: delete the `.dat`
  (`rm "<copy>/Data/moves.dat"`) — Essentials recreates it. Common: `moves.dat`,
  `attacksRS.dat`, `dexdata.dat`, `items.dat`, `metadata.dat`.
- Or **hold Ctrl at the title** for a full PBS recompile.

## Tier 3 — external scripts without repacking Scripts.rxdata (opt-in)

To iterate battle scripts without re-marshalling `Scripts.rxdata`:

1. `mv "<copy>/mkxp.json.loadorder" "<copy>/mkxp.json"` (this enables the
   `load_order` shim; it preloads only `Scripts/load_order_shim.rb` — no Win32
   wrapper needed under Wine).
2. Add your `.rb` file(s) to `<copy>/Scripts/load_order.txt` (one relative path per
   line; `#` comments allowed). They load **before** `Scripts.rxdata`, so they can
   monkey-patch it.
3. Launch — look for `[LOAD_ORDER_SHIM] active` and `loaded N script(s)`.
4. Return to the clean default with `rm "<copy>/mkxp.json"` (removing the root
   `mkxp.json` keeps the keyboard-good baseline).

## Testing in-game (Debug menu)

Boot the debug launcher → pause menu → **Debug** (labels are Spanish):

- *Agregar Pokémon* — spawn any Pokémon
- *Indicar el nivel…* — set a level
- *Llenar Mochila* — fill the bag
- heal / fill party, enable Pokédex, etc.

Use these to stage a behavior spec's `test_cases` in a debug battle.

## Harmless boot noise

"No soundfont specified," "Primary font not found: Arial," and `encountered \r in
middle of line` warnings are cosmetic — ignore them.
