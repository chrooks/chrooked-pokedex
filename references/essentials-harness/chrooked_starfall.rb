# chrooked:starfall
# ---------------------------------------------------------------------------
# Starfall: when this Pokemon deals damage with a SPECIAL move, 30% chance to
# lower the target's Special Defense by 1 stage (special-move analogue of
# POISONTOUCH/POISONPOINT, which live in the same hook).
#
# Seam (verified in Data/Scripts.rxdata, PokeBattle_Battler ~line 1459):
# pbEffectsOnDealingDamage(move,user,target,damage) runs after the USER deals
# damage; vanilla POISONTOUCH and POISONPOINT are applied here. Alias it on
# PokeBattle_Battler.
#   - Gate damage dealt:  damage && damage > 0
#   - Special category:   move.pbIsSpecial?(...) (rescue if unsure)
#   - Roll:               @battle.pbRandom(100) < 30
#   - Apply -1 SPDEF:     target.pbReduceStatWithCause(PBStats::SPDEF,1,user,name)
# PBStats::SPDEF == 5 in this fork. pbReduceStatWithCause returns false when the
# stat is already at -6, so the "can't drop further" case is engine-handled.
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

def chrooked_install_starfall
  return if $chrooked_starfall_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsOnDealingDamage")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffectsOnDealingDamage_chrooked_starfall_orig")
      alias_method :pbEffectsOnDealingDamage_chrooked_starfall_orig, :pbEffectsOnDealingDamage
      def pbEffectsOnDealingDamage(move, user, target, damage)
        pbEffectsOnDealingDamage_chrooked_starfall_orig(move, user, target, damage)
        if move && user && target &&
           damage && damage > 0 &&
           (user.hasWorkingAbility(:STARFALL) rescue false) &&
           (move.pbIsSpecial?(move.pbType(move.type, user, target)) rescue (move.pbIsSpecial? rescue false))
          if @battle.pbRandom(100) < 30
            (target.pbReduceStatWithCause(PBStats::SPDEF, 1, user, PBAbilities.getName(user.ability)) rescue nil)
            ($chrooked_log.call("[chrooked:starfall] OBS event=hit ability=true effect=lowered target SPDEF by 1") rescue nil)
          else
            ($chrooked_log.call("[chrooked:starfall] OBS event=hit ability=true effect=roll failed (>=30), no stat change") rescue nil)
          end
        end
      end
    end
  end
  $chrooked_starfall_installed = true
  ($chrooked_log.call("[chrooked:starfall] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsOnDealingDamage")
  chrooked_install_starfall
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_starfall_orig)
      alias_method :update_chrooked_starfall_orig, :update
      def update
        chrooked_install_starfall if !$chrooked_starfall_installed && defined?(PokeBattle_Battler)
        update_chrooked_starfall_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:starfall] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:starfall] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
