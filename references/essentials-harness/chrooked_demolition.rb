# chrooked:demolition
# ---------------------------------------------------------------------------
# Demolition: KOing a foe with a damaging move raises the user's Attack by 1 and
# Speed by 1 (Moxie clone raising two stats).
#
# Seam (verified in Data/Scripts.rxdata): PokeBattle_Battler#pbEffectsAfterHit
# (vanilla MOXIE's home; gate on user.hasWorkingAbility + target.isFainted?). Stat
# consts PBStats::ATTACK / PBStats::SPEED. pbIncreaseStatWithCause returns false at
# +6, so the "no change when capped" case is engine-handled. pbEffectsAfterHit only
# runs after a damaging hit connected, satisfying "damages but does not KO -> nothing"
# (the isFainted? gate) and "must be a damaging move".
#
# Ruby 1.8: alias_method chaining; deferred install on Graphics.update.
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

def chrooked_install_demolition
  return if $chrooked_demolition_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsAfterHit")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffectsAfterHit_chrooked_demolition_orig")
      alias_method :pbEffectsAfterHit_chrooked_demolition_orig, :pbEffectsAfterHit
      def pbEffectsAfterHit(user, target, thismove, turneffects)
        pbEffectsAfterHit_chrooked_demolition_orig(user, target, thismove, turneffects)
        if user && target && (user.hasWorkingAbility(:DEMOLITION) rescue false) && (target.isFainted? rescue false)
          name = (PBAbilities.getName(user.ability) rescue "Demolition")
          (user.pbIncreaseStatWithCause(PBStats::ATTACK, 1, user, name) rescue nil)
          (user.pbIncreaseStatWithCause(PBStats::SPEED, 1, user, name) rescue nil)
          ($chrooked_log.call("[chrooked:demolition] OBS event=ko ability=true raised=ATTACK,SPEED") rescue nil)
        end
      end
    end
  end
  $chrooked_demolition_installed = true
  ($chrooked_log.call("[chrooked:demolition] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsAfterHit")
  chrooked_install_demolition
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_demolition_orig)
      alias_method :update_chrooked_demolition_orig, :update
      def update
        chrooked_install_demolition if !$chrooked_demolition_installed && defined?(PokeBattle_Battler)
        update_chrooked_demolition_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:demolition] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:demolition] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
