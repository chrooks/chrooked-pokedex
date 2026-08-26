# chrooked:zz_kirinfog
# Kirin compatibility shim — NOT a Ruleset behavior. Hand-placed, not generated.
#
# Symptom: on thor, big maps stutter and the fan spikes when weather is active,
# and there is a sharp hitch when weather transitions in or out. A cloud "fog"
# layer is visible under the rain particles.
#
# Cause: that layer is an RMXP fog — a full-screen image alpha-blended over the
# whole map viewport and re-composited every frame (Spriteset_Map#update reads
# @map.fog_name / @map.fog_opacity each frame). The zz_kirinweather shim tames
# the rain PARTICLES; the fog is a separate, unshimmed layer. The transition
# hitch is the fog PNG being loaded from disk and uploaded to the GPU the
# moment weather starts.
#
# This shim makes Spriteset_Map see no fog at all on Kirin: fog_name reads as
# "" so the bitmap is never loaded, and fog_opacity reads as 0 as a belt-and-
# braces. Gameplay is untouched — RMXP fog is purely visual; weather type,
# field effects, and battle weather read other state.
#
# ponytail: one knob. Flip to false to get the fog back without deleting.
CHROOKED_KIRIN_NO_FOG = true
#
# Revert: delete this file (apply never prunes mods) or flip the knob.
if defined?(Game_Map) && $kirin
  module ChrookedKirinFog
    def fog_name
      CHROOKED_KIRIN_NO_FOG ? "" : super
    end

    def fog_opacity
      CHROOKED_KIRIN_NO_FOG ? 0 : super
    end
  end
  Game_Map.prepend(ChrookedKirinFog)
end
