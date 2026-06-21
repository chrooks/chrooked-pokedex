# chrooked:aerodynamic
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "aerodynamic": a Motor Drive clone
# for Flying. Incoming FLYING-type moves are absorbed (made ineffective, deal
# no damage) and the holder's Speed rises by one stage. Pure single-target
# absorb only.
#
# NOT PORTED (deliberately): the doubles-redirection part (drawing single-target
# Flying moves toward the holder like Lightning Rod / Storm Drain). The spec's
# turn-order effect is out of scope for this harness packet.
#
# Seam (verified 16.2, Data/Scripts.rxdata):
#   PokeBattle_Move#pbTypeImmunityByAbility(type, attacker, opponent) — line 324.
#   Returning true makes the incoming move INEFFECTIVE (the absorb). Bonuses are
#   applied to 'opponent' (the holder being hit). Vanilla SAPSIPPER/MOTORDRIVE
#   gate on pbCanIncreaseStatStage? then pbIncreaseStatWithCause then return true.
#
#   We override via alias_method chaining: call the _orig first; if it already
#   returned true, return true (some other ability/type immunity fired). Else if
#   the holder has AERODYNAMIC and the move's type is Flying -> raise Speed +1 and
#   return true. Otherwise return the _orig result (false).
#
# Second Seam (OBS only, no behavior change):
#   PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — purpose-built
#   final-damage multiplier hook (0x1000 units). We do NOT alter damage here; the
#   Flying immunity is fully handled by the type-immunity hook above. This hook
#   only emits an OBS line so the harness can witness damage-path resolution.
#   result is BOOSTED|WEAKENED|NORMAL by comparing the orig mult to the unit base.
#
# HARNESS (Route B log oracle):
#   absorb hook: [chrooked:aerodynamic] OBS type=<TYPE> ability=true result=ABSORBED
#   damage hook: [chrooked:aerodynamic] OBS move=<NAME> result=BOOSTED|WEAKENED|NORMAL
#
# RUBY 1.8: alias_method chaining; each of the two methods aliased separately and
# installed via a deferred Graphics.update arm with its own installed-flag.
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

# --- Hook 1: the absorb (type immunity + Speed +1) --------------------------
def chrooked_install_aerodynamic_absorb
  return if $chrooked_aerodynamic_absorb_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbTypeImmunityByAbility_chrooked_aerodynamic_orig")
      alias_method :pbTypeImmunityByAbility_chrooked_aerodynamic_orig, :pbTypeImmunityByAbility
      def pbTypeImmunityByAbility(type, attacker, opponent)
        orig = pbTypeImmunityByAbility_chrooked_aerodynamic_orig(type, attacker, opponent)
        return true if orig
        has_aero = (opponent.hasWorkingAbility(:AERODYNAMIC) rescue false)
        is_flying = (isConst?(type, PBTypes, :FLYING) rescue false)
        if has_aero && is_flying
          typename = (getConstantName(PBTypes, type) rescue type.to_s)
          if (opponent.pbCanIncreaseStatStage?(PBStats::SPEED, opponent) rescue false)
            (opponent.pbIncreaseStatWithCause(PBStats::SPEED, 1, opponent, opponent.pbThis) rescue nil)
          end
          ($chrooked_log.call("[chrooked:aerodynamic] OBS type=#{typename} ability=true result=ABSORBED") rescue nil)
          return true
        end
        orig
      end
    end
  end
  $chrooked_aerodynamic_absorb_installed = true
  ($chrooked_log.call("[chrooked:aerodynamic] absorb hook installed on PokeBattle_Move") rescue nil)
end

# --- Hook 2: damage-path OBS (witness only, no behavior change) --------------
def chrooked_install_aerodynamic_damage
  return if $chrooked_aerodynamic_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_aerodynamic_orig")
      alias_method :pbModifyDamage_chrooked_aerodynamic_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_aerodynamic_orig(damagemult, attacker, opponent)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        result = if mult > damagemult
                   "BOOSTED"
                 elsif mult < damagemult
                   "WEAKENED"
                 else
                   "NORMAL"
                 end
        ($chrooked_log.call("[chrooked:aerodynamic] OBS move=#{movename} result=#{result}") rescue nil)
        mult
      end
    end
  end
  $chrooked_aerodynamic_damage_installed = true
  ($chrooked_log.call("[chrooked:aerodynamic] damage hook installed on PokeBattle_Move") rescue nil)
end

# --- Deferred install arming (each hook tracked by its own flag) -------------
if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  chrooked_install_aerodynamic_absorb
  chrooked_install_aerodynamic_damage
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_aerodynamic_orig)
      alias_method :update_chrooked_aerodynamic_orig, :update
      def update
        if defined?(PokeBattle_Move)
          chrooked_install_aerodynamic_absorb if !$chrooked_aerodynamic_absorb_installed
          chrooked_install_aerodynamic_damage if !$chrooked_aerodynamic_damage_installed
        end
        update_chrooked_aerodynamic_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:aerodynamic] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:aerodynamic] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
