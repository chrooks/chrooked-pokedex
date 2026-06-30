# chrooked:carnivore
# ---------------------------------------------------------------------------
# Carnivore (ability :CARNIVORE): knocking out a foe heals the user 1/4 of its
# max HP. Moxie/Hubris-shaped after-KO hook.
#
# Seam: the compat shim's install_after_move bridges 16.2's pbEffectsAfterHit
# (per-target) and IF2's pbEffectsAfterMove (per-move targets list), normalizing
# to one (user, target, move) call per target. On a KO by the user's move, heal
# user.totalhp/4 via pbRecoverHP (floors at max and returns the amount healed, so a
# full-HP user heals 0). Heal Block is gated like Shell Bell (HealBlock effect == 0).
#
# ponytail: skipped the "no heal if the KO ends the battle" guard — healing after
# the last foe faints is invisible, not worth a NoAliveMons check.
#
# RUBY 1.8: install via Chrooked.install_after_move; deferred on Graphics.update.
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
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_carnivore_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_carnivore_apply(user, target, thismove)
        begin
          return unless user && target
          return unless (user.hasWorkingAbility(:CARNIVORE) rescue false)
          fainted = (target.fainted? rescue (target.isFainted? rescue false))
          return unless fainted
          return if (user.fainted? rescue (user.isFainted? rescue false))
          return unless user.effects[PBEffects::HealBlock] == 0
          healed = (user.pbRecoverHP((user.totalhp / 4).floor, true) rescue 0)
          ($chrooked_log.call("[chrooked:carnivore] OBS event=ko ability=true healed=#{healed}") rescue nil)
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_after_move("chrooked_carnivore_apply", "pbAfterMove_chrooked_carnivore_orig")
  $chrooked_carnivore_installed = true
  ($chrooked_log.call("[chrooked:carnivore] installed (after-move seam)") rescue nil)
end

if defined?(PokeBattle_Battler) && defined?(Chrooked)
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
  ($chrooked_log.call("[chrooked:carnivore] ERROR: neither PokeBattle_Battler nor Graphics defined at load") rescue nil)
end
