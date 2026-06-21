# chrooked:flytrap
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "flytrap" (ability :FLYTRAP).
# A two-stat Sap Sipper clone: BUG-type moves are absorbed (made ineffective)
# and, on the absorb, raise BOTH the holder's Attack and Sp. Atk by one stage.
# TWO plugins-in-one, each on a DIFFERENT method of PokeBattle_Move:
#
#   1) ABSORB — PokeBattle_Move#pbTypeImmunityByAbility(type, attacker, opponent):
#      verified Seam (Data/Scripts.rxdata, line 324). Returning true makes the
#      incoming move INEFFECTIVE; the bonus applies to 'opponent' (the holder
#      being hit). We alias-chain: call _orig first; if it already returned true,
#      pass that through; else if 'opponent' has Flytrap AND the resolved move
#      type is Bug, raise ATTACK then SPATK (each gated on pbCanIncreaseStatStage?)
#      and return true; otherwise return the _orig result. Mirrors vanilla
#      SAPSIPPER/MOTORDRIVE exactly, but with two PBStats instead of one.
#
#   2) DAMAGE — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent):
#      a second, independent observation Seam on a DIFFERENT method. Bug moves
#      are absorbed before they reach damage, so this hook never fires for the
#      absorbed case; it exists to give the harness a damage-path log oracle for
#      moves that DO land. It does not alter damage (result=NORMAL); BOOSTED and
#      WEAKENED are reserved labels in the OBS contract.
#
# Both methods are aliased onto PokeBattle_Move with their own _chrooked_flytrap
# names, and BOTH installs are deferred onto Graphics.update with SEPARATE
# installed-flags so they arm regardless of script load order. Mirrors the
# alias/defer/guarded-logger structure of chrooked_kindle.rb and the dual-hook
# arming of chrooked_infernalmaw.rb.
#
# HARNESS (Route B log oracle):
#   absorb hook: [chrooked:flytrap] OBS type=<TYPE> ability=true result=ABSORBED
#   damage hook: [chrooked:flytrap] OBS move=<NAME> result=BOOSTED|WEAKENED|NORMAL
#
# Stat consts: PBStats::ATTACK / PBStats::SPATK (no SPECIAL_ATTACK).
# Helpers (verified): pbCanIncreaseStatStage?, pbIncreaseStatWithCause,
# isConst?(type, PBTypes, :BUG), hasWorkingAbility.
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

# --- Install 1: Bug absorb + dual stat-up on PokeBattle_Move ----------------
def chrooked_install_flytrap_absorb
  return if $chrooked_flytrap_absorb_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbTypeImmunityByAbility_chrooked_flytrap_orig")
      alias_method :pbTypeImmunityByAbility_chrooked_flytrap_orig, :pbTypeImmunityByAbility
      def pbTypeImmunityByAbility(type, attacker, opponent)
        orig = pbTypeImmunityByAbility_chrooked_flytrap_orig(type, attacker, opponent)
        return true if orig
        is_ab = (opponent.hasWorkingAbility(:FLYTRAP) rescue false)
        is_bug = (isConst?(type, PBTypes, :BUG) rescue false)
        if is_ab && is_bug
          if (opponent.pbCanIncreaseStatStage?(PBStats::ATTACK, opponent) rescue false)
            opponent.pbIncreaseStatWithCause(PBStats::ATTACK, 1, opponent, name)
          end
          if (opponent.pbCanIncreaseStatStage?(PBStats::SPATK, opponent) rescue false)
            opponent.pbIncreaseStatWithCause(PBStats::SPATK, 1, opponent, name)
          end
          ($chrooked_log.call("[chrooked:flytrap] OBS type=#{(PBTypes.getName(type) rescue type)} ability=true result=ABSORBED") rescue nil)
          return true
        end
        orig
      end
    end
  end
  $chrooked_flytrap_absorb_installed = true
  ($chrooked_log.call("[chrooked:flytrap] absorb install on PokeBattle_Move") rescue nil)
end

# --- Install 2: damage-path observation on PokeBattle_Move ------------------
def chrooked_install_flytrap_damage
  return if $chrooked_flytrap_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_flytrap_orig")
      alias_method :pbModifyDamage_chrooked_flytrap_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_flytrap_orig(damagemult, attacker, opponent)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        # Bug moves are absorbed before reaching damage, so this is an
        # observation-only oracle: damage is unchanged (NORMAL). BOOSTED and
        # WEAKENED are reserved labels in the OBS contract.
        ($chrooked_log.call("[chrooked:flytrap] OBS move=#{movename} result=NORMAL") rescue nil)
        mult
      end
    end
  end
  $chrooked_flytrap_damage_installed = true
  ($chrooked_log.call("[chrooked:flytrap] damage install on PokeBattle_Move") rescue nil)
end

# --- Arm both installs (immediate if the method is ready, else deferred) ----
if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  chrooked_install_flytrap_absorb
end
if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_flytrap_damage
end

if (!$chrooked_flytrap_absorb_installed || !$chrooked_flytrap_damage_installed) && defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_flytrap_orig)
      alias_method :update_chrooked_flytrap_orig, :update
      def update
        if !$chrooked_flytrap_absorb_installed && defined?(PokeBattle_Move)
          chrooked_install_flytrap_absorb
        end
        if !$chrooked_flytrap_damage_installed && defined?(PokeBattle_Move)
          chrooked_install_flytrap_damage
        end
        update_chrooked_flytrap_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:flytrap] deferred install armed on Graphics.update") rescue nil)
elsif !defined?(Graphics) && (!$chrooked_flytrap_absorb_installed || !$chrooked_flytrap_damage_installed)
  ($chrooked_log.call("[chrooked:flytrap] ERROR: PokeBattle_Move not ready and no Graphics to defer onto") rescue nil)
end
