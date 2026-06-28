# chrooked:mysticblades
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "mysticblades": the user's SLICING
# moves deal 30% more damage, AND physical slicing moves emulate reading the
# user's Sp. Atk instead of Attack (a category-style attack-stat override).
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units. Same Seam kindle uses.
#
# TWO mechanics, both folded into the one multiplier hook:
#   1) BOOST: x1.3 when the move is in the curated slicing set.
#   2) STAT-SWAP EMULATION: when the slicing move is PHYSICAL, the fork would
#      read Sp.Atk in place of Atk inside pbCalcDamage. 16.2 reads the attack
#      stat INLINE (attacker.attack / attacker.spatk, ~lines 891/898) with no
#      clean hook. Because damage is LINEAR in the attack stat, we approximate
#      "read SpAtk instead of Atk" by multiplying damagemult by the ratio of the
#      staged Sp.Atk to the staged Atk. This is an APPROXIMATION — it ignores
#      crit stage-clamping and accumulates rounding error vs a true inline swap,
#      so it WARRANTS AN IN-GAME CHECK.
#
# Slicing has NO engine flag in 16.2, so the gate is a curated move-symbol set
# matched via isConst?(@id, PBMoves, sym).
#
# Staged stat = (base * stagemul[stage+6] / stagediv[stage+6]).floor, the same
# table pbCalcDamage uses. Guard against divide-by-zero on the Atk denominator.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:mysticblades] OBS move=<NAME> ability=<t|f> result=<BOOSTED|NORMAL>
# Cases distinguished by move: slicing move + ability -> BOOSTED; else -> NORMAL.
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

# Curated SLICING move set (no slicing flag exists in 16.2).
unless defined?($CHROOKED_MYSTICBLADES_MOVES)
  $CHROOKED_MYSTICBLADES_MOVES = [
    :XSCISSOR, :NIGHTSLASH, :SLASH, :AIRSLASH, :LEAFBLADE, :PSYCHOCUT,
    :SACREDSWORD, :SOLARBLADE, :CROSSPOISON, :FURYCUTTER, :CUT,
    :RAZORSHELL, :BEHEMOTHBLADE, :CEASELESSEDGE, :KOWTOWCLEAVE
  ]
end

# Staged-stat tables (mirror pbCalcDamage). Index is stage+6, stage in [-6,6].
unless defined?($CHROOKED_STAGEMUL)
  $CHROOKED_STAGEMUL = [10, 10, 10, 10, 10, 10, 10, 15, 20, 25, 30, 35, 40]
  $CHROOKED_STAGEDIV = [40, 35, 30, 25, 20, 15, 10, 10, 10, 10, 10, 10, 10]
end

def chrooked_install_mysticblades
  return if $chrooked_mysticblades_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_mysticblades_orig")
      alias_method :pbModifyDamage_chrooked_mysticblades_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_mysticblades_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:MYSTICBLADES) rescue false)
        is_slicing = $CHROOKED_MYSTICBLADES_MOVES.any? { |s| (isConst?(@id, PBMoves, s) rescue false) }
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && is_slicing
          # 1) BOOST: x1.3 for any slicing move.
          mult = (mult * 1.3).round
          # 2) STAT-SWAP EMULATION: physical only — rescale by staged spatk/atk.
          movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
          is_physical = (Chrooked.move_physical?(self, movetype) rescue false)
          if is_physical
            atk_stage  = (attacker.stages[PBStats::ATTACK] rescue 0)
            spa_stage  = (attacker.stages[PBStats::SPATK]  rescue 0)
            base_atk   = (attacker.attack rescue 0)
            base_spatk = (attacker.spatk  rescue 0)
            staged_atk   = (base_atk   * $CHROOKED_STAGEMUL[atk_stage + 6] / $CHROOKED_STAGEDIV[atk_stage + 6]).floor
            staged_spatk = (base_spatk * $CHROOKED_STAGEMUL[spa_stage + 6] / $CHROOKED_STAGEDIV[spa_stage + 6]).floor
            # Guard divide-by-zero (e.g. 0 Atk after drops / unusual state).
            if staged_atk > 0
              # APPROXIMATION of an inline Atk->SpAtk read; warrants in-game check.
              mult = (mult * staged_spatk / staged_atk.to_f).round
            end
          end
          ($chrooked_log.call("[chrooked:mysticblades] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:mysticblades] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_mysticblades_installed = true
  ($chrooked_log.call("[chrooked:mysticblades] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_mysticblades
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_mysticblades_orig)
      alias_method :update_chrooked_mysticblades_orig, :update
      def update
        chrooked_install_mysticblades if !$chrooked_mysticblades_installed && defined?(PokeBattle_Move)
        update_chrooked_mysticblades_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:mysticblades] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:mysticblades] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
