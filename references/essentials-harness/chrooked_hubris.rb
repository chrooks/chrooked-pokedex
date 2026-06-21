# chrooked:hubris
# ---------------------------------------------------------------------------
# Hubris: KOing a foe raises the user's Special Attack by 1 (Moxie clone — Moxie
# raises ATTACK; Hubris raises SPATK).
#
# Seam (verified in Data/Scripts.rxdata): PokeBattle_Battler#pbEffectsAfterHit —
# vanilla MOXIE lives here ("if user.hasWorkingAbility(:MOXIE) && target.isFainted?
# ... user.pbIncreaseStatWithCause(PBStats::ATTACK,1,user,name)"). Stat const is
# PBStats::SPATK (this fork has no SPECIAL_ATTACK). pbIncreaseStatWithCause returns
# false when already +6, so the "no boost when maxed" case is handled by the engine.
#
# Ruby 1.8: alias_method chaining; deferred install on Graphics.update (the shim
# preloads before PokeBattle_Battler is defined).
# ---------------------------------------------------------------------------

unless defined?($chrooked_log) && $chrooked_log
  $chrooked_log = lambda do |msg|
    begin
      d = File.expand_path(File.dirname(__FILE__))
      File.open(File.join(d, "chrooked_load.log"), "a") { |f| f.puts(msg) }
    rescue Exception
    end
  end
end

def chrooked_install_hubris
  return if $chrooked_hubris_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsAfterHit")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffectsAfterHit_chrooked_hubris_orig")
      alias_method :pbEffectsAfterHit_chrooked_hubris_orig, :pbEffectsAfterHit
      def pbEffectsAfterHit(user, target, thismove, turneffects)
        pbEffectsAfterHit_chrooked_hubris_orig(user, target, thismove, turneffects)
        if user && target && (user.hasWorkingAbility(:HUBRIS) rescue false) && (target.isFainted? rescue false)
          (user.pbIncreaseStatWithCause(PBStats::SPATK, 1, user, PBAbilities.getName(user.ability)) rescue nil)
          ($chrooked_log.call("[chrooked:hubris] OBS event=ko ability=true raised=SPATK") rescue nil)
        end
      end
    end
  end
  $chrooked_hubris_installed = true
  ($chrooked_log.call("[chrooked:hubris] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsAfterHit")
  chrooked_install_hubris
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_hubris_orig)
      alias_method :update_chrooked_hubris_orig, :update
      def update
        chrooked_install_hubris if !$chrooked_hubris_installed && defined?(PokeBattle_Battler)
        update_chrooked_hubris_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:hubris] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:hubris] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
