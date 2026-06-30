# chrooked:hubris
# ---------------------------------------------------------------------------
# Hubris (ability :HUBRIS): KOing a foe raises the user's Special Attack by 1
# (Moxie clone — Moxie raises Attack; Hubris raises SpAtk).
#
# Seam: compat shim's install_after_move (16.2 pbEffectsAfterHit / IF2
# pbEffectsAfterMove), normalized to one (user, target, move) call per target. Gate
# on user ability + target fainted. SpAtk raise goes through Chrooked.raise_stat
# (16.2 PBStats::SPATK / IF2 :SPECIAL_ATTACK); the engine no-ops at +6.
#
# Ruby 1.8: install via Chrooked.install_after_move; deferred on Graphics.update.
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
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_hubris_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_hubris_apply(user, target, thismove)
        begin
          return unless user && target
          return unless (user.hasWorkingAbility(:HUBRIS) rescue false)
          fainted = (target.fainted? rescue (target.isFainted? rescue false))
          return unless fainted
          Chrooked.raise_stat(user, :spatk, 1, user)
          ($chrooked_log.call("[chrooked:hubris] OBS event=ko ability=true raised=SPATK") rescue nil)
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_after_move("chrooked_hubris_apply", "pbAfterMove_chrooked_hubris_orig")
  $chrooked_hubris_installed = true
  ($chrooked_log.call("[chrooked:hubris] installed (after-move seam)") rescue nil)
end

if defined?(PokeBattle_Battler) && defined?(Chrooked)
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
  ($chrooked_log.call("[chrooked:hubris] ERROR: neither PokeBattle_Battler nor Graphics defined at load") rescue nil)
end
