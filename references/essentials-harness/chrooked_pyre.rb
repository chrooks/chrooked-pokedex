# chrooked:pyre
# ---------------------------------------------------------------------------
# Pyre (ability :PYRE): this Pokemon's Ghost-type moves gain a 30% chance to burn
# the target. ATTACKER-side, after-hit status roll.
#
# Redefined 2026-06-30. The old mechanic (KO arms a 3-turn Fire/Ghost 1.3x damage
# window) is fully removed — no more pbModifyDamage boost, no KO timer, no
# switch-in reset ivar.
#
# Seam: the compat shim's install_after_move bridges 16.2's pbEffectsAfterHit
# (per-target) and IF2's pbEffectsAfterMove (per-move targets list), normalizing to
# one (user, target, move) call per target. Damage dealt is read from
# target.damageState.hpLost (present on both engines). Move type resolved via
# Chrooked.move_type so renamed-engine type reads still work.
#
# HARNESS (Route B log oracle): on a damaging Ghost move from a Pyre user, logs:
#     [chrooked:pyre] OBS move=<NAME> type=GHOST ability=true burn=<true|false>
#
# RUBY 1.8: install via Chrooked.install_after_move; deferred on Graphics.update.
# ---------------------------------------------------------------------------

CHROOKED_PYRE_BURN_CHANCE = 30

unless defined?($chrooked_log) && $chrooked_log
  $chrooked_log = lambda do |msg|
    begin
      d = File.expand_path(File.dirname(__FILE__))
      File.open(File.join(d, "chrooked_load.log"), "a") { |f| f.puts(msg) }
    rescue Exception
    end
  end
end

def chrooked_install_pyre
  return if $chrooked_pyre_installed
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_pyre_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_pyre_apply(user, target, thismove)
        begin
          return unless user && target
          return unless (user.hasWorkingAbility(:PYRE) rescue false)
          dealt = (target.damageState.hpLost rescue 0)
          dealt = 0 if dealt.nil?
          return unless dealt > 0
          movetype = (Chrooked.move_type(thismove, user, target) rescue nil)
          is_ghost = (isConst?(movetype, PBTypes, :GHOST) rescue false)
          return unless is_ghost
          if @battle.pbRandom(100) < CHROOKED_PYRE_BURN_CHANCE
            can_burn = (target.pbCanBurn?(user, false, thismove) rescue false)
            target.pbBurn(user) if can_burn
            ($chrooked_log.call("[chrooked:pyre] OBS move=#{(thismove.name rescue thismove)} type=GHOST ability=true burn=#{can_burn}") rescue nil)
          end
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_after_move("chrooked_pyre_apply", "pbAfterMove_chrooked_pyre_orig")
  $chrooked_pyre_installed = true
  ($chrooked_log.call("[chrooked:pyre] installed (after-move seam)") rescue nil)
end

if defined?(PokeBattle_Battler) && defined?(Chrooked)
  chrooked_install_pyre
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_pyre_orig)
      alias_method :update_chrooked_pyre_orig, :update
      def update
        chrooked_install_pyre if !$chrooked_pyre_installed && defined?(PokeBattle_Battler)
        update_chrooked_pyre_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:pyre] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:pyre] ERROR: neither PokeBattle_Battler nor Graphics defined at load") rescue nil)
end
