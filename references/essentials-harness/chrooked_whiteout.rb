# chrooked:whiteout
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "whiteout": in HAIL, the user's moves
# that use its higher attacking stat deal 50% more damage. If Attack >= Sp.Atk,
# physical moves get the x1.5; otherwise (Sp.Atk > Attack) special moves get it.
# The tie (Attack == Sp.Atk) resolves to the PHYSICAL branch.
#
# Single hook. Stateless: every gate is read live in the damage step, so there is
# NO per-battler ivar — therefore no pbAbilitiesOnSwitchIn reset is needed.
#
# Seam (verified 16.2): PokeBattle_Move#pbModifyDamage(damagemult, attacker,
#   opponent). damagemult is in 0x1000 units; base impl just returns it. Here
#   `attacker` is the user (ATTACKER ability -> attacker.hasWorkingAbility).
#   Gates, matching the SPEC exactly:
#     attacker.hasWorkingAbility(:WHITEOUT)
#       and @battle.pbWeather == PBWeather::HAIL
#       and ( (pbIsPhysical?(movetype) and attacker.attack >= attacker.spatk)
#          or (pbIsSpecial?(movetype)  and attacker.spatk  > attacker.attack) )
#   then mult = (mult * 1.5).round.
#   movetype = pbType(@type, attacker, opponent).
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#   [chrooked:whiteout] OBS move=<NAME> whiteout=<bool> hail=<bool> phys=<bool>
#     spec=<bool> atk=<n> spatk=<n> result=<BOOSTED|NORMAL>
#
# RUBY 1.8: alias_method chaining; own installed-flag; deferred install on
# Graphics.update; unique _chrooked_whiteout names; call _orig first.
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

# --- Hook: hail higher-attacking-stat x1.5 damage boost ---------------------
def chrooked_install_whiteout_damage
  return if $chrooked_whiteout_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_whiteout_orig")
      alias_method :pbModifyDamage_chrooked_whiteout_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_whiteout_orig(damagemult, attacker, opponent)
        is_whiteout = (attacker.hasWorkingAbility(:WHITEOUT) rescue false)
        is_hail = (@battle.pbWeather == PBWeather::HAIL rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_phys = (pbIsPhysical?(movetype) rescue false)
        is_spec = (pbIsSpecial?(movetype) rescue false)
        atk = (attacker.attack rescue 0)
        spatk = (attacker.spatk rescue 0)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        higher_phys = (is_phys && atk >= spatk)
        higher_spec = (is_spec && spatk > atk)
        if is_whiteout && is_hail && (higher_phys || higher_spec)
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:whiteout] OBS move=#{movename} whiteout=#{is_whiteout} hail=#{is_hail} phys=#{is_phys} spec=#{is_spec} atk=#{atk} spatk=#{spatk} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:whiteout] OBS move=#{movename} whiteout=#{is_whiteout} hail=#{is_hail} phys=#{is_phys} spec=#{is_spec} atk=#{atk} spatk=#{spatk} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_whiteout_damage_installed = true
  ($chrooked_log.call("[chrooked:whiteout] damage hook installed on PokeBattle_Move") rescue nil)
end

# --- Deferred install arming (tracked by its own flag) ----------------------
if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_whiteout_damage
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_whiteout_orig)
      alias_method :update_chrooked_whiteout_orig, :update
      def update
        chrooked_install_whiteout_damage if !$chrooked_whiteout_damage_installed && defined?(PokeBattle_Move)
        update_chrooked_whiteout_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:whiteout] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:whiteout] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
