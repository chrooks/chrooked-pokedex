# chrooked:magicalfists
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "magicalfists": the user's punching
# moves deal 30% more damage (x1.3) AND — when the punch is PHYSICAL — the move
# reads the user's Sp. Atk (and its Sp. Atk stat stages) in place of Attack.
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units. Same Seam as kindle/hammerfist (proves
# generality). Mirrors chrooked_kindle.rb's alias / defer / logger structure.
#
# GATE: ability :MAGICALFISTS  AND  isPunchingMove? (verified 16.2 move flag).
#
# TWO independent effects when the gate matches:
#   1. POWER BOOST — multiply damagemult by 1.3 (always, punch is punch).
#   2. ATTACK-STAT SWAP (PHYSICAL punches only) — *** EMULATION, needs in-game
#      verify ***. pbCalcDamage reads atk = attacker.attack (physical) or
#      attacker.spatk (special) INLINE; there is no clean hook to substitute the
#      stat. Because damage is LINEAR in the attack stat, we approximate the
#      "read Sp. Atk instead of Atk" swap by rescaling damagemult by
#      (staged_spatk / staged_atk) for physical punches.
#
#      Staged stat = (base * stagemul[stage+6] / stagediv[stage+6]).floor, with
#        stagemul = [10,10,10,10,10,10,10,15,20,25,30,35,40]
#        stagediv = [40,35,30,25,20,15,10,10,10,10,10,10,10]
#      stage = attacker.stages[PBStats::ATTACK] / [PBStats::SPATK].
#      Guard divide-by-zero (staged_atk == 0 -> skip the swap).
#
#      *** APPROXIMATION CAVEAT — IN-GAME VERIFY REQUIRED ***
#      This rescale reproduces the swap only to the precision damagemult allows:
#      it re-applies stage multipliers AFTER the engine already applied the Attack
#      stage, so rounding differs slightly from a true inline stat substitution,
#      and it does NOT mirror the crit-rule that ignores unfavorable attack stages
#      inside pbCalcDamage. Treat the swap as an emulation pending an in-game check
#      (high-SpAtk / low-Atk punch should out-damage the same punch read off Atk).
#
# Type / category resolution: movetype = pbType(@type, attacker, opponent);
# physical test via pbIsPhysical?(movetype) (verified 16.2 helpers).
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:magicalfists] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: punching move + ability -> BOOSTED; else NORMAL.
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

# Konami-standard 16.2 stage tables (index = stage + 6, stage in -6..+6).
CHROOKED_MAGICALFISTS_STAGEMUL = [10, 10, 10, 10, 10, 10, 10, 15, 20, 25, 30, 35, 40]
CHROOKED_MAGICALFISTS_STAGEDIV = [40, 35, 30, 25, 20, 15, 10, 10, 10, 10, 10, 10, 10]

# Staged stat = (base * stagemul[stage+6] / stagediv[stage+6]).floor.
def chrooked_staged_stat_chrooked_magicalfists(base, stage)
  idx = stage + 6
  idx = 0 if idx < 0
  idx = 12 if idx > 12
  (base * CHROOKED_MAGICALFISTS_STAGEMUL[idx] / CHROOKED_MAGICALFISTS_STAGEDIV[idx]).floor
end

def chrooked_install_magicalfists
  return if $chrooked_magicalfists_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_magicalfists_orig")
      alias_method :pbModifyDamage_chrooked_magicalfists_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_magicalfists_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:MAGICALFISTS) rescue false)
        is_punch = (isPunchingMove? rescue false)
        gate = is_ab && is_punch
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if gate
          # Effect 1: unconditional 1.3x power boost for punching moves.
          mult = (mult * 1.3).round
          # Effect 2 (PHYSICAL only): emulate the Atk->SpAtk stat swap by
          # rescaling. *** EMULATION — see header caveat, needs in-game verify ***
          movetype = (pbType(@type, attacker, opponent) rescue -1)
          is_physical = (pbIsPhysical?(movetype) rescue false)
          if is_physical
            begin
              atk_stage   = attacker.stages[PBStats::ATTACK]
              spatk_stage = attacker.stages[PBStats::SPATK]
              staged_atk   = chrooked_staged_stat_chrooked_magicalfists(attacker.attack, atk_stage)
              staged_spatk = chrooked_staged_stat_chrooked_magicalfists(attacker.spatk, spatk_stage)
              if staged_atk > 0   # guard divide-by-zero
                mult = (mult * staged_spatk / staged_atk.to_f).round
              end
            rescue Exception
              # If anything in the swap emulation blows up, keep the 1.3x boost
              # and fall through; never crash the damage calc.
            end
          end
          ($chrooked_log.call("[chrooked:magicalfists] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:magicalfists] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_magicalfists_installed = true
  ($chrooked_log.call("[chrooked:magicalfists] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_magicalfists
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_magicalfists_orig)
      alias_method :update_chrooked_magicalfists_orig, :update
      def update
        chrooked_install_magicalfists if !$chrooked_magicalfists_installed && defined?(PokeBattle_Move)
        update_chrooked_magicalfists_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:magicalfists] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:magicalfists] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
