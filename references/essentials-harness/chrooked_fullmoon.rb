# chrooked:fullmoon
# ---------------------------------------------------------------------------
# Full Moon: the user's Dark- and Fairy-type moves get the Same-Type Attack
# Bonus (x1.5) regardless of the user's own types ("pseudo-STAB").
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# final-damage multiplier hook (base impl returns damagemult unchanged; same Seam
# kindle uses). damagemult is in 0x1000 units. movetype = pbType(@type, attacker,
# opponent); type check via isConst?(movetype, PBTypes, :DARK/:FAIRY).
#
# DOUBLE-COUNT GUARD: vanilla STAB is INLINE in pbCalcDamage (if the attacker
# pbHasType?(type) it already multiplied by 1.5). So Full Moon must grant the
# 1.5x ONLY when the gate matches AND the attacker does NOT already have that
# type — otherwise a Dark-type with Full Moon using a Dark move would get 2.25x.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:fullmoon] OBS move=<NAME> fullmoon=<true|false> type=<NAME> result=<BOOSTED|NORMAL>
# Dark/Fairy move + fullmoon + type-not-already-owned -> BOOSTED; else NORMAL.
#
# RUBY 1.8: alias_method chaining; deferred install on Graphics.update.
#
# NOT-PORTED: the second Full Moon effect (Moonlight heals 3/4 maxHP) is keyed on
# the Moonlight move's function-code recover handler, which has NO clean ability
# Seam to alias in this fork. Implementing it would require guessing an unverified
# move-effect method name. Left unported; needs in-game wiring. See partial.
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

def chrooked_install_fullmoon
  return if $chrooked_fullmoon_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_fullmoon_orig")
      alias_method :pbModifyDamage_chrooked_fullmoon_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_fullmoon_orig(damagemult, attacker, opponent)
        is_fullmoon = (attacker.hasWorkingAbility(:FULLMOON) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_dark = (isConst?(movetype, PBTypes, :DARK) rescue false)
        is_fairy = (isConst?(movetype, PBTypes, :FAIRY) rescue false)
        already_has = (attacker.pbHasType?(movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        typename = (getConstantName(PBTypes, movetype) rescue movetype.to_s)
        if is_fullmoon && (is_dark || is_fairy) && !already_has
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:fullmoon] OBS move=#{movename} fullmoon=#{is_fullmoon} type=#{typename} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:fullmoon] OBS move=#{movename} fullmoon=#{is_fullmoon} type=#{typename} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_fullmoon_installed = true
  ($chrooked_log.call("[chrooked:fullmoon] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_fullmoon
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_fullmoon_orig)
      alias_method :update_chrooked_fullmoon_orig, :update
      def update
        chrooked_install_fullmoon if !$chrooked_fullmoon_installed && defined?(PokeBattle_Move)
        update_chrooked_fullmoon_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:fullmoon] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:fullmoon] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
