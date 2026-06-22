# chrooked:permafrost
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "permafrost" (ability :PERMAFROST).
# DEFENDER super-effective damage reducer — a Solid Rock / Filter / Prism Armor
# clone, but reduces to 0.65x instead of the mainline 0.75x.
#
# Single hook on PokeBattle_Move:
#
# HOOK (SE reduction) — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent)
#   16.2 Seam (Data/Scripts.rxdata). In pbModifyDamage, `attacker` is the user
#   and `opponent` is the DEFENDER being hit — so we check the DEFENDER's ability
#   via opponent.hasWorkingAbility(:PERMAFROST). Super-effective on the defender
#   is gated on opponent.damagestate.typemod > 8 (base-8 effectiveness scale; the
#   exact gate Prism Armor / Filter / Solid Rock use). When both hold, scale the
#   final multiplier by 0.65 and round. damagemult is in 0x1000 units.
#
# STATE: none. The gate is read live from opponent.damagestate.typemod, so there
# is no per-battler ivar and therefore NO pbAbilitiesOnSwitchIn reset is needed.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:permafrost] OBS move=<NAME> typemod=<N> result=<REDUCED|NORMAL>
#   SE hit on a Permafrost holder -> REDUCED; otherwise NORMAL.
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

# --- HOOK: super-effective reduction via pbModifyDamage ---------------------
def chrooked_install_permafrost_reduce
  return if $chrooked_permafrost_reduce_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_permafrost_orig")
      alias_method :pbModifyDamage_chrooked_permafrost_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_permafrost_orig(damagemult, attacker, opponent)
        # opponent is the DEFENDER in pbModifyDamage.
        has_permafrost = (opponent.hasWorkingAbility(:PERMAFROST) rescue false)
        typemod = (opponent.damagestate.typemod rescue 0)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if has_permafrost && typemod > 8
          mult = (mult * 0.65).round
          ($chrooked_log.call("[chrooked:permafrost] OBS move=#{movename} typemod=#{typemod} result=REDUCED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:permafrost] OBS move=#{movename} typemod=#{typemod} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_permafrost_reduce_installed = true
  ($chrooked_log.call("[chrooked:permafrost] reduce installed on PokeBattle_Move") rescue nil)
end

def chrooked_install_permafrost_all
  chrooked_install_permafrost_reduce
end

def chrooked_permafrost_all_installed?
  $chrooked_permafrost_reduce_installed
end

if defined?(PokeBattle_Move) &&
   PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_permafrost_all
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_permafrost_orig)
      alias_method :update_chrooked_permafrost_orig, :update
      def update
        chrooked_install_permafrost_all if !chrooked_permafrost_all_installed? && defined?(PokeBattle_Move)
        update_chrooked_permafrost_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:permafrost] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:permafrost] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
