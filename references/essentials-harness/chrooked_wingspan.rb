# chrooked:wingspan
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "wingspan": the user's wing/wind
# moves deal 30% more damage. Single 1.3x multiplier (not stacked when a move
# is both wing and wind).
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units. We scale it by 1.3 when the attacker has
# Wingspan AND the move is in the curated wing/wind set.
#
# GATE: 16.2 PBS has no engine-standard wing/wind move flags, so we gate on a
# curated set of real Essentials PBS move constants. A missing constant simply
# means that move isn't boosted (graceful — the isConst? rescue swallows it).
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:wingspan] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: wing/wind move + Wingspan -> BOOSTED; other -> NORMAL.
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

# Curated wing/wind move-name set. Real Essentials PBS move constants (uppercase,
# no spaces). Each is checked with isConst? so an absent constant is harmless.
CHROOKED_WINGSPAN_MOVES = [
  :WINGATTACK, :AERIALACE, :AIRSLASH, :HURRICANE, :GUST, :AIRCUTTER,
  :BRAVEBIRD, :DRILLPECK, :ACROBATICS, :BOUNCE, :FLY, :DUALWINGBEAT,
  :PECK, :PLUCK, :BEAKBLAST, :FLOATYFALL, :OBLIVIONWING, :DRAGONASCENT,
  :SKYATTACK, :TWISTER, :TAILWIND
] unless defined?(CHROOKED_WINGSPAN_MOVES)

def chrooked_wingspan_gate_match?(move_id)
  CHROOKED_WINGSPAN_MOVES.any? { |s| (isConst?(move_id, PBMoves, s) rescue false) }
end

def chrooked_install_wingspan
  return if $chrooked_wingspan_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_wingspan_orig")
      alias_method :pbModifyDamage_chrooked_wingspan_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_wingspan_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:WINGSPAN) rescue false)
        gate_ok = (chrooked_wingspan_gate_match?(@id) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && gate_ok
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:wingspan] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:wingspan] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_wingspan_installed = true
  ($chrooked_log.call("[chrooked:wingspan] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_wingspan
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_wingspan_orig)
      alias_method :update_chrooked_wingspan_orig, :update
      def update
        chrooked_install_wingspan if !$chrooked_wingspan_installed && defined?(PokeBattle_Move)
        update_chrooked_wingspan_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:wingspan] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:wingspan] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
