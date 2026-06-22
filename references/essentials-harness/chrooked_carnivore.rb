# chrooked:carnivore
# ---------------------------------------------------------------------------
# Carnivore (ability :CARNIVORE): knocking out a foe heals the user 1/4 of its
# max HP. Moxie/Hubris-shaped after-hit KO hook.
#
# Seam (verified in Data/Scripts.rxdata): PokeBattle_Battler#pbEffectsAfterHit
# (line ~1722) — same hook vanilla MOXIE uses ("user.hasWorkingAbility(:MOXIE)
# && target.isFainted?"). On a KO by the user's move, heal user.totalhp/4 via
# pbRecoverHP (line 762; it floors the +HP at max and returns the amount healed,
# so a full-HP user heals 0 — spec test 3 handled by the engine). Heal Block is
# gated exactly like Shell Bell at line 1746 (user.effects[PBEffects::HealBlock]==0).
#
# ponytail: skipped the "no heal if the KO ends the battle" guard — healing after
# the last foe faints is invisible (battle's already over), not worth a NoAliveMons check.
#
# RUBY 1.8: alias_method chaining; deferred install on Graphics.update.
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

def chrooked_install_carnivore
  return if $chrooked_carnivore_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsAfterHit")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffectsAfterHit_chrooked_carnivore_orig")
      alias_method :pbEffectsAfterHit_chrooked_carnivore_orig, :pbEffectsAfterHit
      def pbEffectsAfterHit(user, target, thismove, turneffects)
        pbEffectsAfterHit_chrooked_carnivore_orig(user, target, thismove, turneffects)
        begin
          if user && target && (user.hasWorkingAbility(:CARNIVORE) rescue false) &&
             (target.isFainted? rescue false) && !(user.isFainted? rescue false) &&
             user.effects[PBEffects::HealBlock] == 0
            healed = (user.pbRecoverHP((user.totalhp / 4).floor, true) rescue 0)
            ($chrooked_log.call("[chrooked:carnivore] OBS event=ko ability=true healed=#{healed}") rescue nil)
          end
        rescue Exception
        end
      end
    end
  end
  $chrooked_carnivore_installed = true
  ($chrooked_log.call("[chrooked:carnivore] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsAfterHit")
  chrooked_install_carnivore
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_carnivore_orig)
      alias_method :update_chrooked_carnivore_orig, :update
      def update
        chrooked_install_carnivore if !$chrooked_carnivore_installed && defined?(PokeBattle_Battler)
        update_chrooked_carnivore_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:carnivore] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:carnivore] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
