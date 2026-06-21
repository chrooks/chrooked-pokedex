# chrooked:striker
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "striker": the user's KICKING moves
# deal 30% more damage. Keys off a curated kicking-move-name set, not type.
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units. We scale it by 1.3 when the attacker has Striker
# AND the move is in the curated kicking set. 16.2 has no isKickingMove? flag
# predicate, so we gate on a name set of real Essentials PBS move constants.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:striker] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: kicking move + Striker -> BOOSTED; else -> NORMAL.
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

# Curated kicking-move set — real Essentials PBS move constants (uppercase, no
# spaces). A constant that doesn't exist in this engine simply never matches, so
# the gate degrades gracefully rather than erroring.
$CHROOKED_STRIKER_KICKS = [
  :DOUBLEKICK, :MEGAKICK, :JUMPKICK, :HIGHJUMPKICK, :ROLLINGKICK,
  :BLAZEKICK, :TRIPLEKICK, :LOWKICK, :LOWSWEEP, :STOMP, :TROPKICK
]

def chrooked_is_kicking_move_chrooked_striker(move)
  $CHROOKED_STRIKER_KICKS.any? { |s| (isConst?(move.id, PBMoves, s) rescue false) }
end

def chrooked_install_striker
  return if $chrooked_striker_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_striker_orig")
      alias_method :pbModifyDamage_chrooked_striker_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_striker_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:STRIKER) rescue false)
        is_kick = $CHROOKED_STRIKER_KICKS.any? { |s| (isConst?(@id, PBMoves, s) rescue false) }
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && is_kick
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:striker] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:striker] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_striker_installed = true
  ($chrooked_log.call("[chrooked:striker] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_striker
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_striker_orig)
      alias_method :update_chrooked_striker_orig, :update
      def update
        chrooked_install_striker if !$chrooked_striker_installed && defined?(PokeBattle_Move)
        update_chrooked_striker_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:striker] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:striker] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
