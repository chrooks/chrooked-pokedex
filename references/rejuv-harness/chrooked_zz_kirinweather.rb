# chrooked:zz_kirinweather
# Kirin compatibility shim — NOT a Ruleset behavior. Hand-placed, not generated.
#
# Symptom: under Kirin the overworld stops redrawing while menus, input and audio
# keep working. A NEW GAME is fine; a loaded save is not.
#
# Cause: the save carries active weather. Rejuv's AdvancedWeather (RPG::Weather,
# Scripts/AdvancedWeather.rb, 5464 lines) does two expensive things per frame,
# and only for non-Clear weather:
#
#   1. @viewport.tone.set(-max*3/4, ...)   <- a NON-ZERO tone on the MAP viewport,
#      re-applied every single frame. Menus sit on a different viewport with no
#      tone, which is exactly why they stay smooth while the map stalls.
#   2. (1..@max).each { ... sprite.bitmap = @rain_splash ... }  <- a texture
#      rebind per sprite per frame. Chris's save had :Rain at max 36; his Clear
#      saves sit at max 4.
#
# The pool is 500 Sprite objects allocated up front regardless of @max, and
# `max=` walks all 500 on every weather change.
#
# This shim keeps @weather_type intact, so Field Effects and every battle
# interaction that reads the weather are UNCHANGED. It only reduces what gets
# drawn.
#
# ponytail: two knobs, no rewrite. Tune these two constants if it is still slow
# (lower the max) or if you want the rain tint back (flip FLAT to false).
CHROOKED_KIRIN_WEATHER_MAX  = 6     # sprite cap; game asks for up to 500
CHROOKED_KIRIN_WEATHER_FLAT = true  # true = drop the per-frame full-screen tone
#
# Revert: delete this file. Apply never prunes mods, so remove it by hand.
if defined?(RPG) && defined?(RPG::Weather) && $kirin
  module ChrookedKirinWeather
    def max=(value)
      # Never clamp to 0 — the :Sunny branch disposes the whole sprite pool at 0
      # and never rebuilds it, which breaks weather for the rest of the session.
      super([value.to_i, CHROOKED_KIRIN_WEATHER_MAX].min.clamp(1, 500))
    end

    def update
      super
      # Undo the non-zero map-viewport tone the base update just applied.
      @viewport.tone.set(0, 0, 0, 0) if CHROOKED_KIRIN_WEATHER_FLAT && @viewport
    end
  end
  RPG::Weather.prepend(ChrookedKirinWeather)
end
