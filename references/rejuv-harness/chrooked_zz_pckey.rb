# chrooked:zz_pckey
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
#
# PC hotkey: press P (mnemonic: P for PC) to open the PC storage screen in
# organize mode — on the overworld map AND in the party screen. Same screen
# the party-menu "PC" option (chrooked_zz_pc.rb) opens. The raw P key is
# unbound in Rejuv's default keyboard map (Controls.rb: C/X/Q/W/Tab/M/F7),
# and letter scancodes work with triggerex? (TextEntry.rb uses :C/:V).
# F8 stays the party-screen level-cap key (chrooked_zz_levelcap.rb).
#
# Pad hotkey: Select (SDL calls it BACK on an Xbox-style pad) does the same, so
# the screen is reachable when streaming to a handheld with no keyboard. It has
# to be a separate check: mkxp-z's F1 binding dialog maps pad buttons to game
# *actions*, never to keystrokes, so no pad button can ever produce :P. Pad
# state lives behind Input::Controller, guarded with defined? because the
# stub-test harness has no such module.
#
# Overworld: uses the designed Seam Scene_Map#checkKeyPresses/
# #handleKeyPresses ("to be overwritten per game", Scene_Map.rb:250).
# Rejuv's Blessings overlay already overwrites them
# (Rejuv/Xenpurgis/BlessingsOverlay.rb:318), and Mods load after all base
# scripts, so alias-and-chain keeps the Blessings hotkey working.
#
# Party screen: chains onto PokemonScreen_Scene#update, the same shape the
# base game's Remote PC hold-A path uses inside the choose loop
# (open storage over the scene, then pbHardRefresh). Loads after
# chrooked_zz_levelcap.rb (alphabetical), so the alias chain holds both keys.
#
# Guards: not while an event runs (pbMapInterpreterRunning?), not while
# playing as a story character (:NotPlayerCharacter), and never in battle.
class Game_Temp
  attr_accessor :chrooked_pc_calling
end

module ChrookedPCKey
  # One place both call sites ask, so the keyboard and pad hotkeys can never
  # drift apart.
  def self.pressed?
    return true if Input.triggerex?(:P)
    return false unless defined?(Input::Controller)

    Input::Controller.triggerex?(:BACK)
  end
end

class Scene_Map
  # Chain only when the base Seam exists — the stub-test harness loads this
  # file against bare stand-in classes with no key-press methods.
  if method_defined?(:checkKeyPresses) && !method_defined?(:chrooked_pckey_checkKeyPresses)
    alias chrooked_pckey_checkKeyPresses checkKeyPresses
    alias chrooked_pckey_handleKeyPresses handleKeyPresses

    def checkKeyPresses
      chrooked_pckey_checkKeyPresses
      if ChrookedPCKey.pressed? && !pbMapInterpreterRunning? &&
         !$game_switches[:NotPlayerCharacter]
        $game_temp.chrooked_pc_calling = true
      end
    end

    def handleKeyPresses
      if $game_temp.chrooked_pc_calling
        $game_temp.chrooked_pc_calling = false
        $game_player.straighten
        pbFadeOutIn(99999) {
          PokemonStorageScreen.new(PokemonStorageScene.new, $PokemonStorage).pbStartScreen(0)
        }
      else
        chrooked_pckey_handleKeyPresses
      end
    end
  end
end

class PokemonScreen_Scene
  if method_defined?(:update) && !method_defined?(:chrooked_pckey_update)
    alias chrooked_pckey_update update

    def update
      chrooked_pckey_update
      # busy guard: message loops call self.update reentrantly
      return if @chrooked_pckey_busy || !ChrookedPCKey.pressed?
      return if $game_temp.in_battle || $game_switches[:NotPlayerCharacter]

      @chrooked_pckey_busy = true
      begin
        pbFadeOutIn(99999) {
          PokemonStorageScreen.new(PokemonStorageScene.new, $PokemonStorage).pbStartScreen(0)
        }
        pbHardRefresh
      ensure
        @chrooked_pckey_busy = false
      end
    end
  end
end
