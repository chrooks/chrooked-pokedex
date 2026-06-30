# chrooked:spitefulblock
# ---------------------------------------------------------------------------
# Spiteful Block: taking a damaging hit arms a one-time +30% boost on this
# Pokemon's NEXT Dark-type move. The boost is consumed (flag cleared) the moment
# a Dark move uses it in damage-calc. Being hit again before spending it does not
# stack — it just keeps the flag TRUE.
#
# Three Seams (all verified in Data/Scripts.rxdata), so this is a multi-hook
# port. Each hook is aliased separately with its own installed-flag and its own
# deferred Graphics.update arming.
#
#   (a) ARM — PokeBattle_Battler#pbEffectsOnDealingDamage(move,user,target,damage)
#       runs after the USER deals damage to TARGET (same hook as vanilla
#       POISONTOUCH/POISONPOINT). Here `self` is the user; the Pokemon that just
#       got hit is `target`. So we check the DEFENDER's ability on `target`:
#       target.hasWorkingAbility(:SPITEFULBLOCK) && damage>0 -> set the defender's
#       ivar @chrooked_spitefulblock_flag = true.
#
#   (b) CONSUME — PokeBattle_Move#pbModifyDamage(damagemult,attacker,opponent)
#       is 16.2's final-damage multiplier hook (0x1000 units). Here `attacker` is
#       the user of THIS move (the ATTACKER ability/flag side). If
#       attacker.hasWorkingAbility(:SPITEFULBLOCK) && its flag is true &&
#       the resolved movetype is DARK -> mult = (mult*1.3).round and clear the
#       flag (set it back to false). movetype = pbType(@type,attacker,opponent);
#       DARK gate via isConst?(movetype,PBTypes,:DARK).
#
#   (c) RESET — PokeBattle_Battler#pbAbilitiesOnSwitchIn(onactive). The flag is a
#       plain battler ivar with no PBEffects slot, so it must be reset on
#       switch-in or it would leak to the next Pokemon in that slot. We set it
#       back to its default (false) here.
#
# CUSTOM STATE: @chrooked_spitefulblock_flag, lazily defaulted to false via a
# helper (@chrooked_spitefulblock_flag = false unless defined? / ||= idiom).
#
# OBS log fires on each gate firing:
#     [chrooked:spitefulblock] OBS ...
#
# Ruby 1.8: alias_method chaining; deferred install on Graphics.update; unique
# _chrooked_spitefulblock_ names; original called first.
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

# --- (a) ARM: set the defender's flag when it takes a damaging hit ----------
def chrooked_install_spitefulblock_arm
  return if $chrooked_spitefulblock_arm_installed
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_spitefulblock_arm_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_spitefulblock_arm_apply(move, user, target, damage)
        begin
          if target && damage && damage > 0 &&
             (target.hasWorkingAbility(:SPITEFULBLOCK) rescue false)
            target.instance_variable_set(:@chrooked_spitefulblock_flag, true)
            ($chrooked_log.call("[chrooked:spitefulblock] OBS event=hit ability=true effect=armed (next Dark move +30%)") rescue nil)
          end
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_post_damage("chrooked_spitefulblock_arm_apply", "pbOnDamage_chrooked_spitefulblock_orig")
  $chrooked_spitefulblock_arm_installed = true
  ($chrooked_log.call("[chrooked:spitefulblock] arm hook installed (post-damage seam)") rescue nil)
end

# --- (b) CONSUME: boost the armed Dark move, then clear the flag ------------
def chrooked_install_spitefulblock_consume
  return if $chrooked_spitefulblock_consume_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_spitefulblock_orig")
      alias_method :pbModifyDamage_chrooked_spitefulblock_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_spitefulblock_orig(damagemult, attacker, opponent)
        begin
          is_spite = (attacker.hasWorkingAbility(:SPITEFULBLOCK) rescue false)
          armed = (attacker.instance_variable_get(:@chrooked_spitefulblock_flag) rescue false) ? true : false
          movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
          is_dark = (isConst?(movetype, PBTypes, :DARK) rescue false)
          if is_spite && armed && is_dark
            movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
            mult = (mult * 1.3).round
            attacker.instance_variable_set(:@chrooked_spitefulblock_flag, false)
            ($chrooked_log.call("[chrooked:spitefulblock] OBS event=consume move=#{movename} ability=true armed=true type=DARK result=BOOSTED+30% (flag cleared)") rescue nil)
          end
        rescue Exception
        end
        mult
      end
    end
  end
  $chrooked_spitefulblock_consume_installed = true
  ($chrooked_log.call("[chrooked:spitefulblock] consume hook installed on PokeBattle_Move#pbModifyDamage") rescue nil)
end

# --- (c) RESET: clear the ivar on switch-in so it does not leak -------------
# Via the compat shim's install_switch_in (16.2 pbAbilitiesOnSwitchIn / IF2
# pbEffectsOnSwitchIn); apply receives the switched-in flag.
def chrooked_install_spitefulblock_reset
  return if $chrooked_spitefulblock_reset_installed
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_spitefulblock_reset_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_spitefulblock_reset_apply(switched_in)
        begin
          return unless switched_in   # only a REAL switch-in
          self.instance_variable_set(:@chrooked_spitefulblock_flag, false)
          ($chrooked_log.call("[chrooked:spitefulblock] OBS event=switchin effect=flag reset to default(false)") rescue nil)
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_switch_in("chrooked_spitefulblock_reset_apply", "pbSwitchIn_chrooked_spitefulblock_orig")
  $chrooked_spitefulblock_reset_installed = true
  ($chrooked_log.call("[chrooked:spitefulblock] reset hook installed (switch-in seam)") rescue nil)
end

def chrooked_install_spitefulblock_all
  chrooked_install_spitefulblock_arm
  chrooked_install_spitefulblock_consume
  chrooked_install_spitefulblock_reset
end

def chrooked_spitefulblock_all_installed?
  $chrooked_spitefulblock_arm_installed &&
    $chrooked_spitefulblock_consume_installed &&
    $chrooked_spitefulblock_reset_installed
end

# Install now if both classes are already defined, else defer to Graphics.update.
if defined?(PokeBattle_Battler) && defined?(PokeBattle_Move)
  chrooked_install_spitefulblock_all
end

if !chrooked_spitefulblock_all_installed? && defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_spitefulblock_orig)
      alias_method :update_chrooked_spitefulblock_orig, :update
      def update
        chrooked_install_spitefulblock_all if !chrooked_spitefulblock_all_installed?
        update_chrooked_spitefulblock_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:spitefulblock] deferred install armed on Graphics.update") rescue nil)
elsif !chrooked_spitefulblock_all_installed?
  ($chrooked_log.call("[chrooked:spitefulblock] ERROR: PokeBattle_Battler/PokeBattle_Move/Graphics missing at load") rescue nil)
end
