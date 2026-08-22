# chrooked:zz_kirincull — Kirin compatibility shim, hand-placed (not generated).
#
# Rejuv's Spriteset_Map#update deliberately updates EVERY event sprite every
# frame; the in_range? cull is commented out in base code over a sticky-sprite
# bug in Reborn's KotH. On Kirin that costs ~200ms/frame (5fps) on dense city
# maps. This restores the cull, Kirin-only, with the sticky case handled by
# hiding the sprite while culled.
#
# Alias chain, not prepend — a prepend on Sprite_Character recursed (Rejuv
# alias-chains this class after mods load).
CHROOKED_KIRIN_CULL_MARGIN = 128  # px beyond the screen edge that still updates
class Sprite_Character
  unless method_defined?(:chrooked_kirincull_update)
    alias chrooked_kirincull_update update

    def update
      if $kirin && @character.is_a?(Game_Event)
        m = CHROOKED_KIRIN_CULL_MARGIN
        sx = @character.screen_x
        sy = @character.screen_y
        if sx < -m || sx > Graphics.width + m || sy < -m || sy > Graphics.height + m
          self.visible = false if self.visible  # no stale sprite parked on screen
          return
        end
      end
      chrooked_kirincull_update
    end
  end
end
