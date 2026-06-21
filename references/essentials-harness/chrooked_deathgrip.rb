# chrooked:deathgrip
# ---------------------------------------------------------------------------
# Death Grip: when this Pokemon deals damage with a CONTACT move, 30% chance to
# apply a Wrap/Bind trap to the target if it isn't already trapped.
#
# Seam (verified in Data/Scripts.rxdata): PokeBattle_Battler#pbEffectsOnDealingDamage
# (move,user,target,damage) — runs after USER deals damage. Vanilla POISONTOUCH and
# POISONPOINT both live here. Alias it on PokeBattle_Battler.
#
# Gates: damage && damage>0 (damage actually dealt), move.isContactMove? (contact),
# and the 30% roll @battle.pbRandom(100)<30. Trap is the Wrap-style volatile: only
# set when target.effects[PBEffects::MultiTurn]==0, then MultiTurn (5..6 turns),
# MultiTurnAttack (move id), MultiTurnUser (user index).
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

def chrooked_install_deathgrip
  return if $chrooked_deathgrip_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsOnDealingDamage")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffectsOnDealingDamage_chrooked_deathgrip_orig")
      alias_method :pbEffectsOnDealingDamage_chrooked_deathgrip_orig, :pbEffectsOnDealingDamage
      def pbEffectsOnDealingDamage(move, user, target, damage)
        pbEffectsOnDealingDamage_chrooked_deathgrip_orig(move, user, target, damage)
        begin
          if move && user && target && damage && damage > 0 &&
             (user.hasWorkingAbility(:DEATHGRIP) rescue false) &&
             (move.isContactMove? rescue false)
            if @battle.pbRandom(100) < 30
              if (target.effects[PBEffects::MultiTurn] rescue 0) == 0
                target.effects[PBEffects::MultiTurn]       = 5 + @battle.pbRandom(2)
                target.effects[PBEffects::MultiTurnAttack] = (move.id rescue @id)
                target.effects[PBEffects::MultiTurnUser]   = user.index
                ($chrooked_log.call("[chrooked:deathgrip] OBS event=hit ability=true effect=trapped target") rescue nil)
              else
                ($chrooked_log.call("[chrooked:deathgrip] OBS event=hit ability=true effect=already-trapped no-op") rescue nil)
              end
            else
              ($chrooked_log.call("[chrooked:deathgrip] OBS event=hit ability=true effect=roll-failed no trap") rescue nil)
            end
          end
        rescue Exception
          ($chrooked_log.call("[chrooked:deathgrip] OBS event=hit ability=true effect=error rescued") rescue nil)
        end
      end
    end
  end
  $chrooked_deathgrip_installed = true
  ($chrooked_log.call("[chrooked:deathgrip] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsOnDealingDamage")
  chrooked_install_deathgrip
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_deathgrip_orig)
      alias_method :update_chrooked_deathgrip_orig, :update
      def update
        chrooked_install_deathgrip if !$chrooked_deathgrip_installed && defined?(PokeBattle_Battler)
        update_chrooked_deathgrip_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:deathgrip] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:deathgrip] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
