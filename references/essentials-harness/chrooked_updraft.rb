# chrooked:updraft
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "updraft". Two independent hooks:
#
#   HOOK 1 (Ground immunity, Levitate-like): an incoming GROUND-type move is
#   made INEFFECTIVE (absorbed) with NO bonus to the holder. Pure block.
#
#   HOOK 2 (wind/wing boost, Wingspan-like): when the holder USES a wind/wing
#   move (curated set), the move's final damage is multiplied by 1.3.
#
# Two different Seams on PokeBattle_Move, each aliased separately with its own
# deferred install and its own installed-flag:
#
#   Seam 1: PokeBattle_Move#pbTypeImmunityByAbility(type, attacker, opponent)
#     — 16.2 returns true to make the incoming move INEFFECTIVE (the absorb),
#     normally applying a bonus to 'opponent' (the holder being hit). Verified
#     in Data/Scripts.rxdata, line 324. Vanilla examples: SAPSIPPER (GRASS) ups
#     opponent ATTACK then returns true; MOTORDRIVE (ELECTRIC) ups SPEED;
#     VOLT/WATERABSORB heal; LEVITATE-style = bare `return true` (no bonus).
#     We chain _orig FIRST: if it returns true the move is already absorbed by
#     some other ability — pass it through. Otherwise, if the holder has Updraft
#     and the incoming move type is GROUND, return true (pure block, no bonus).
#     Else return the _orig result (false).
#
#   Seam 2: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent)
#     — 16.2's final-damage multiplier hook (base impl just returns damagemult;
#     damagemult is in 0x1000 units). We scale by 1.3 when the attacker has
#     Updraft AND the move is in the curated wind/wing set. 16.2 PBS has no
#     engine-standard wind/wing flag, so we gate on a curated set of real
#     Essentials PBS move constants (each checked with isConst?, so an absent
#     constant is harmless).
#
# Helpers verified present: pbCanIncreaseStatStage? / pbIncreaseStatWithCause /
# pbRecoverHP (used by vanilla absorbs; Updraft uses none of them since it is a
# pure block), isConst?(type, PBTypes, :X), hasWorkingAbility, getConstantName.
#
# HARNESS (Route B log oracle):
#   Hook 1 logs on the absorb path:
#     [chrooked:updraft] OBS type=<TYPE> ability=true result=ABSORBED
#   Hook 2 logs on every pbModifyDamage call:
#     [chrooked:updraft] OBS move=<NAME> result=<BOOSTED|WEAKENED|NORMAL>
#   (WEAKENED is part of the contract for symmetry with damage-modifying hooks;
#   Updraft only ever BOOSTS or leaves NORMAL.)
#
# RUBY 1.8: alias_method chaining; two deferred installs on Graphics.update.
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

# Curated wind/wing move-name set. Real Essentials PBS move constants (uppercase,
# no spaces). Each is checked with isConst? so an absent constant is harmless.
CHROOKED_UPDRAFT_MOVES = [
  :WINGATTACK, :AERIALACE, :AIRSLASH, :HURRICANE, :GUST, :AIRCUTTER,
  :BRAVEBIRD, :DRILLPECK, :ACROBATICS, :BOUNCE, :FLY, :DUALWINGBEAT,
  :PECK, :PLUCK, :BEAKBLAST, :FLOATYFALL, :OBLIVIONWING, :DRAGONASCENT,
  :SKYATTACK, :TWISTER, :TAILWIND, :BLEAKWINDSTORM, :SANDSEARSTORM,
  :WILDBOLTSTORM, :SPRINGTIDESTORM, :FAIRYWIND, :PETALBLIZZARD, :BLIZZARD,
  :HEATWAVE, :ICYWIND, :RAZORWIND, :WHIRLWIND, :DEFOG
] unless defined?(CHROOKED_UPDRAFT_MOVES)

def chrooked_updraft_gate_match?(move_id)
  CHROOKED_UPDRAFT_MOVES.any? { |s| (isConst?(move_id, PBMoves, s) rescue false) }
end

# --- HOOK 1: Ground immunity (absorb) on pbTypeImmunityByAbility -------------
def chrooked_install_updraft_immunity
  return if $chrooked_updraft_immunity_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbTypeImmunityByAbility_chrooked_updraft_orig")
      alias_method :pbTypeImmunityByAbility_chrooked_updraft_orig, :pbTypeImmunityByAbility
      def pbTypeImmunityByAbility(type, attacker, opponent)
        orig = pbTypeImmunityByAbility_chrooked_updraft_orig(type, attacker, opponent)
        return true if orig
        is_updraft = (opponent.hasWorkingAbility(:UPDRAFT) rescue false)
        is_ground = (isConst?(type, PBTypes, :GROUND) rescue false)
        if is_updraft && is_ground
          ($chrooked_log.call("[chrooked:updraft] OBS type=GROUND ability=true result=ABSORBED") rescue nil)
          return true
        end
        orig
      end
    end
  end
  $chrooked_updraft_immunity_installed = true
  ($chrooked_log.call("[chrooked:updraft] immunity hook installed on PokeBattle_Move") rescue nil)
end

# --- HOOK 2: wind/wing 1.3x boost on pbModifyDamage -------------------------
def chrooked_install_updraft_boost
  return if $chrooked_updraft_boost_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_updraft_orig")
      alias_method :pbModifyDamage_chrooked_updraft_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_updraft_orig(damagemult, attacker, opponent)
        is_updraft = (attacker.hasWorkingAbility(:UPDRAFT) rescue false)
        gate_ok = (chrooked_updraft_gate_match?(@id) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_updraft && gate_ok
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:updraft] OBS move=#{movename} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:updraft] OBS move=#{movename} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_updraft_boost_installed = true
  ($chrooked_log.call("[chrooked:updraft] boost hook installed on PokeBattle_Move") rescue nil)
end

# --- Install / deferred-install both hooks independently ---------------------
if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  chrooked_install_updraft_immunity
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_updraft_immunity_orig)
      alias_method :update_chrooked_updraft_immunity_orig, :update
      def update
        chrooked_install_updraft_immunity if !$chrooked_updraft_immunity_installed && defined?(PokeBattle_Move)
        update_chrooked_updraft_immunity_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:updraft] deferred immunity install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:updraft] ERROR: neither PokeBattle_Move nor Graphics defined at load (immunity)") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_updraft_boost
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_updraft_boost_orig)
      alias_method :update_chrooked_updraft_boost_orig, :update
      def update
        chrooked_install_updraft_boost if !$chrooked_updraft_boost_installed && defined?(PokeBattle_Move)
        update_chrooked_updraft_boost_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:updraft] deferred boost install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:updraft] ERROR: neither PokeBattle_Move nor Graphics defined at load (boost)") rescue nil)
end
