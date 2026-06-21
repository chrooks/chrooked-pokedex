# chrooked:stonebark
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "stonebark" (ability :STONEBARK).
# Two hooks on PokeBattle_Move, each its own alias chain + installed-flag:
#
# HOOK 1 (absorb) — PokeBattle_Move#pbTypeImmunityByAbility(type, attacker, opponent)
#   16.2 Seam (Data/Scripts.rxdata, line 324). Returning true makes the incoming
#   move INEFFECTIVE; the bonus applies to `opponent` (the holder being hit).
#   Modeled on WATERABSORB/VOLTABSORB: if opponent has STONEBARK and the move's
#   type is GRASS, and Heal Block is not active, restore 1/4 max HP, then return
#   true (absorb). Vanilla aliased _orig is called first so SAPSIPPER / LEVITATE
#   / native immunities still fire — if _orig returns true we pass it through.
#
# HOOK 2 (Water weakness) — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent)
#   In pbModifyDamage, `opponent` is the DEFENDER. If the defender has STONEBARK
#   and the move's resolved type is WATER, scale the final multiplier by 1.25.
#   damagemult is in 0x1000 units; we round after scaling.
#
# HARNESS (Route B log oracle):
#   absorb:  [chrooked:stonebark] OBS type=<TYPE> ability=true result=ABSORBED
#   damage:  [chrooked:stonebark] OBS move=<NAME> result=BOOSTED|WEAKENED|NORMAL
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

# --- HOOK 1: Grass absorb via pbTypeImmunityByAbility ----------------------
def chrooked_install_stonebark_absorb
  return if $chrooked_stonebark_absorb_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbTypeImmunityByAbility_chrooked_stonebark_orig")
      alias_method :pbTypeImmunityByAbility_chrooked_stonebark_orig, :pbTypeImmunityByAbility
      def pbTypeImmunityByAbility(type, attacker, opponent)
        orig = pbTypeImmunityByAbility_chrooked_stonebark_orig(type, attacker, opponent)
        return true if orig
        has_stonebark = (opponent.hasWorkingAbility(:STONEBARK) rescue false)
        is_grass = (isConst?(type, PBTypes, :GRASS) rescue false)
        typename = (getConstantName(PBTypes, type) rescue type.to_s)
        if has_stonebark && is_grass
          if (opponent.effects[PBEffects::HealBlock] rescue 0) == 0
            (opponent.pbRecoverHP((opponent.totalhp / 4).floor, true) rescue nil)
          end
          ($chrooked_log.call("[chrooked:stonebark] OBS type=#{typename} ability=true result=ABSORBED") rescue nil)
          return true
        end
        orig
      end
    end
  end
  $chrooked_stonebark_absorb_installed = true
  ($chrooked_log.call("[chrooked:stonebark] absorb installed on PokeBattle_Move") rescue nil)
end

# --- HOOK 2: Water weakness via pbModifyDamage -----------------------------
def chrooked_install_stonebark_weakness
  return if $chrooked_stonebark_weakness_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_stonebark_orig")
      alias_method :pbModifyDamage_chrooked_stonebark_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_stonebark_orig(damagemult, attacker, opponent)
        # opponent is the DEFENDER in pbModifyDamage.
        has_stonebark = (opponent.hasWorkingAbility(:STONEBARK) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_water = (isConst?(movetype, PBTypes, :WATER) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if has_stonebark && is_water
          mult = (mult * 1.25).round
          ($chrooked_log.call("[chrooked:stonebark] OBS move=#{movename} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:stonebark] OBS move=#{movename} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_stonebark_weakness_installed = true
  ($chrooked_log.call("[chrooked:stonebark] weakness installed on PokeBattle_Move") rescue nil)
end

def chrooked_install_stonebark_all
  chrooked_install_stonebark_absorb
  chrooked_install_stonebark_weakness
end

def chrooked_stonebark_all_installed?
  $chrooked_stonebark_absorb_installed && $chrooked_stonebark_weakness_installed
end

if defined?(PokeBattle_Move) &&
   PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility") &&
   PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_stonebark_all
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_stonebark_orig)
      alias_method :update_chrooked_stonebark_orig, :update
      def update
        chrooked_install_stonebark_all if !chrooked_stonebark_all_installed? && defined?(PokeBattle_Move)
        update_chrooked_stonebark_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:stonebark] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:stonebark] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
