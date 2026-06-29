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
  return unless defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_starfall_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_starfall_apply(move, user, target, damage)
        if move && user && target &&
           damage && damage > 0 &&
           (user.hasWorkingAbility(:STARFALL) rescue false) &&
           (Chrooked.move_special?(move, Chrooked.move_type(move, user, target)) rescue false)
          if @battle.pbRandom(100) < 30
            (Chrooked.lower_stat(target, :spdef, 1, user) rescue nil)
            ($chrooked_log.call("[chrooked:starfall] OBS event=hit ability=true effect=lowered target SPDEF by 1") rescue nil)
          else
            ($chrooked_log.call("[chrooked:starfall] OBS event=hit ability=true effect=roll failed (>=30), no stat change") rescue nil)
          end
        end
      end
    end
  end
  return unless Chrooked.install_post_damage("chrooked_starfall_apply", "pbOnDamage_chrooked_starfall_orig")
  $chrooked_starfall_installed = true
  ($chrooked_log.call("[chrooked:starfall] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && defined?(Chrooked)
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
