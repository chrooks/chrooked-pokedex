# chrooked:highnoon
# ---------------------------------------------------------------------------
# High Noon: the solar counterpart to Full Moon. This Pokemon's FIRE- and
# PSYCHIC-type moves get pseudo-STAB (a flat 1.5x), regardless of the user's
# own types. (The Morning Sun 75%-heal branch is NOT-PORTED — see note below.)
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units.
#
# DOUBLE-COUNT GUARD: vanilla STAB is applied INLINE in pbCalcDamage (x1.5 when
# attacker.pbHasType?(type)). To GRANT pseudo-STAB without double-counting, we
# multiply by 1.5 ONLY when the move type is FIRE or PSYCHIC AND the attacker
# does NOT already have that type (if they already have it, vanilla STAB already
# gave the 1.5). So a Fire/Normal High Noon user firing Flamethrower keeps the
# vanilla 1.5 and we add nothing; a pure-Normal High Noon user gets our 1.5.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:highnoon] OBS move=<NAME> highnoon=<true|false> gate=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: Fire/Psychic move + highnoon + no own-type-match
# -> BOOSTED; otherwise -> NORMAL.
#
# RUBY 1.8: alias_method chaining; deferred install on Graphics.update.
# ---------------------------------------------------------------------------
#
# NOT-PORTED: "When this Pokemon uses Morning Sun, it recovers 75% of max HP."
# No verified Seam for the Morning Sun recover routine was supplied in FACTS
# (the Cmd_recoverbasedonsunlight equivalent / Essentials Morning Sun recover
# handler method name is unverified). Per instructions, do NOT guess unverified
# method names — leaving this branch unimplemented. The pseudo-STAB half is fully
# ported above.
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

def chrooked_install_highnoon
  return if $chrooked_highnoon_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_highnoon_orig")
      alias_method :pbModifyDamage_chrooked_highnoon_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_highnoon_orig(damagemult, attacker, opponent)
        is_highnoon = (attacker.hasWorkingAbility(:HIGHNOON) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_fire = (isConst?(movetype, PBTypes, :FIRE) rescue false)
        is_psychic = (isConst?(movetype, PBTypes, :PSYCHIC) rescue false)
        # Vanilla STAB already gives 1.5 if the user already has the move's type;
        # only grant pseudo-STAB when they do NOT, to avoid double-counting.
        already_stab = (attacker.pbHasType?(movetype) rescue false)
        gate = is_highnoon && (is_fire || is_psychic) && !already_stab
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if gate
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:highnoon] OBS move=#{movename} highnoon=#{is_highnoon} gate=true result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:highnoon] OBS move=#{movename} highnoon=#{is_highnoon} gate=false result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_highnoon_installed = true
  ($chrooked_log.call("[chrooked:highnoon] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_highnoon
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_highnoon_orig)
      alias_method :update_chrooked_highnoon_orig, :update
      def update
        chrooked_install_highnoon if !$chrooked_highnoon_installed && defined?(PokeBattle_Move)
        update_chrooked_highnoon_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:highnoon] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:highnoon] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
