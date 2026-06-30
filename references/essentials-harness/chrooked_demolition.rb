# chrooked:demolition
# ---------------------------------------------------------------------------
# Demolition (ability :DEMOLITION): KOing a foe with a damaging move raises the
# user's Attack by 1 and Speed by 1 (Moxie clone raising two stats).
#
# Seam: compat shim's install_after_move (16.2 pbEffectsAfterHit / IF2
# pbEffectsAfterMove), normalized to one (user, target, move) call per target. Gate
# on user ability + target fainted. Stat raises go through Chrooked.raise_stat
# (16.2 pbIncreaseStatWithCause / IF2 pbRaiseStatStage); the engine no-ops at +6.
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

def chrooked_install_demolition
  return if $chrooked_demolition_installed
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_demolition_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_demolition_apply(user, target, thismove)
        begin
          return unless user && target
          return unless (user.hasWorkingAbility(:DEMOLITION) rescue false)
          fainted = (target.fainted? rescue (target.isFainted? rescue false))
          return unless fainted
          Chrooked.raise_stat(user, :attack, 1, user)
          Chrooked.raise_stat(user, :speed, 1, user)
          ($chrooked_log.call("[chrooked:demolition] OBS event=ko ability=true raised=ATTACK,SPEED") rescue nil)
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_after_move("chrooked_demolition_apply", "pbAfterMove_chrooked_demolition_orig")
  $chrooked_demolition_installed = true
  ($chrooked_log.call("[chrooked:demolition] installed (after-move seam)") rescue nil)
end

if defined?(PokeBattle_Battler) && defined?(Chrooked)
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
  ($chrooked_log.call("[chrooked:demolition] ERROR: neither PokeBattle_Battler nor Graphics defined at load") rescue nil)
end
