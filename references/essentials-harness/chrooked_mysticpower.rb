# chrooked:mysticpower
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "mysticpower": every DAMAGING move the
# user makes gets the Same-Type Attack Bonus (1.5x), regardless of the user's own
# types. Pseudo-STAB for any move.
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# final-damage multiplier hook (base impl returns damagemult; verified in the
# extracted 084_PokeBattle_Move). damagemult is in 0x1000 units. We call _orig
# first, then scale by 1.5 when the gate matches.
#
# GATE (single hook):
#   - attacker.hasWorkingAbility(:MYSTICPOWER)
#   - the move is damaging (not status): pbIsPhysical?(movetype) || pbIsSpecial?(movetype)
#   - NOT attacker.pbHasType?(movetype)
#       Vanilla STAB is INLINE in pbCalcDamage (x1.5 when attacker.pbHasType?(type)).
#       If the user already has the move's type, vanilla already granted 1.5 — so we
#       must NOT add another 1.5 (no double-count). We only grant the bonus when the
#       user does NOT match the type, replicating STAB for off-type moves.
#
# HARNESS (Route B log oracle): every gate firing logs one line:
#     [chrooked:mysticpower] OBS move=<NAME> mysticpower=<true|false> ...
#       result=BOOSTED  -> pseudo-STAB granted (off-type damaging move)
#       result=NORMAL   -> no bonus (not ability / status move / already has type)
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

def chrooked_install_mysticpower
  return if $chrooked_mysticpower_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_mysticpower_orig")
      alias_method :pbModifyDamage_chrooked_mysticpower_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_mysticpower_orig(damagemult, attacker, opponent)
        is_mystic = (attacker.hasWorkingAbility(:MYSTICPOWER) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_damaging = ((pbIsPhysical?(movetype) || pbIsSpecial?(movetype)) rescue false)
        already_has_type = (attacker.pbHasType?(movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_mystic && is_damaging && !already_has_type
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:mysticpower] OBS move=#{movename} mysticpower=#{is_mystic} damaging=#{is_damaging} hastype=#{already_has_type} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:mysticpower] OBS move=#{movename} mysticpower=#{is_mystic} damaging=#{is_damaging} hastype=#{already_has_type} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_mysticpower_installed = true
  ($chrooked_log.call("[chrooked:mysticpower] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_mysticpower
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_mysticpower_orig)
      alias_method :update_chrooked_mysticpower_orig, :update
      def update
        chrooked_install_mysticpower if !$chrooked_mysticpower_installed && defined?(PokeBattle_Move)
        update_chrooked_mysticpower_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:mysticpower] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:mysticpower] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
