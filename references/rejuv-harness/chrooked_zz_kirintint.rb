# chrooked:zz_kirintint — Kirin compatibility shim, hand-placed (not generated).
#
# Diagnosis (probe v3, 2026-08-22): outdoor maps run at ~5fps on Kirin with
# ~200ms/frame inside Spriteset_Map#update, while tilemap=0ms and weather=0ms.
# Indoor/new-game maps run at the full 40fps cap. Cause: RPG_Sprite.rb calls
# pbDayNightTint(self) for EVERY character sprite EVERY frame on outdoor maps,
# and a non-zero per-sprite tone forces an extra shader pass per sprite —
# ruinous on Kirin's GLES renderer with ~100 events on a city map.
#
# This override (Modding.txt: mod files override individual functions) keeps
# vanilla behavior everywhere except under Kirin, where the day/night tint on
# sprites is dropped and tone writes are skipped when already zero.
# Cost: character sprites lose the day/night color grade on Kirin. Maps and
# battles are unaffected.
def pbDayNightTint(object, outdoor = $game_map.outdoor)
  return unless $scene.is_a?(Scene_Map)

  if ENABLESHADING && outdoor && !$kirin && (!$joiplay || $Settings.performanceMode == 1)
    tone = PBDayNight.getTone()
    object.tone.set(tone.red, tone.green, tone.blue, tone.gray)
  else
    t = object.tone
    # ponytail: skip the write when already zero — tone.set dirties the sprite.
    object.tone.set(0, 0, 0, 0) unless t.red == 0 && t.green == 0 && t.blue == 0 && t.gray == 0
  end
end
