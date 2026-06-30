# chrooked:stampede
# ---------------------------------------------------------------------------
# Stampede (ability :STAMPEDE): knocking out a target arms a one-time +1 priority
# for the user's NEXT contact move; the arming is consumed when a contact move is
# actually used. Stateful, ATTACKER-side.
#
# Per-battler state has no spare PBEffects slot, so the armed flag is a plain ivar
# @chrooked_stampede_armed (default nil = false). Three hooks:
#
#   (a) PRIORITY — PokeBattle_Battle#pbPriority (line 1058). Same Seam and
#       wrap-and-restore technique as chrooked_rapidcombustion (turn order reads
#       @choices[i][2].priority + inline ability bonuses at 1104-1112, not
#       Move#pbPriority). Bump +1 when the user has STAMPEDE, is armed, and the
#       chosen move makes contact (move.isContactMove?, flag 0x01 at Move line 231).
#       priority is attr_reader → set @priority ivar, restore after the sort.
#       Short-circuit when @usepriority is already set (cached order) so we never
#       double-bump.
#
#   (b) ARM/CONSUME — PokeBattle_Battler#pbEffectsAfterHit (line ~1722). Read the
#       armed state BEFORE mutating: if armed AND this move made contact, consume
#       (clear) — the priority for this turn was already applied at round start.
#       THEN if the target fainted, arm. So a contact-KO leaves the flag armed for
#       the next contact move (spec: "the NEXT contact move").
#
#   (c) RESET — PokeBattle_Battler#pbAbilitiesOnSwitchIn(onactive), gated on
#       onactive (this fires every turn with onactive=false otherwise and would
#       wipe state mid-battle). Clear the flag so it never leaks to the next mon.
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

# --- Hook (a): +1 priority for an armed contact move ------------------------
def chrooked_install_stampede_priority
  return if $chrooked_stampede_priority_installed
  return unless defined?(PokeBattle_Battle)
  return unless PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbPriority")
  PokeBattle_Battle.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbPriority_chrooked_stampede_orig")
      alias_method :pbPriority_chrooked_stampede_orig, :pbPriority
      # chrooked: forward args verbatim — IF2's fork rewrote pbPriority to 0..1 args
      # (onlySpeedSort); 16.2 is 0..2 (ignorequickclaw, log). *args matches both.
      def pbPriority(*args)
        return pbPriority_chrooked_stampede_orig(*args) if @usepriority
        bumped = []
        begin
          for i in 0...@choices.length
            next unless @choices[i] && @choices[i][0] == 1 && @choices[i][2]
            move = @choices[i][2]
            batt = @battlers[i]
            next unless batt
            next unless (batt.hasWorkingAbility(:STAMPEDE) rescue false)
            armed = (batt.instance_variable_get(:@chrooked_stampede_armed) rescue false) ? true : false
            contact = (Chrooked.contact_move?(move) rescue (move.isContactMove? rescue false))
            movename = (getConstantName(PBMoves, move.id) rescue "?")
            if armed && contact
              base = move.priority
              move.instance_variable_set(:@priority, base + 1)
              bumped.push([move, base])
              ($chrooked_log.call("[chrooked:stampede] OBS move=#{movename} armed=#{armed} contact=#{contact} result=BOOSTED") rescue nil)
            else
              ($chrooked_log.call("[chrooked:stampede] OBS move=#{movename} armed=#{armed} contact=#{contact} result=NORMAL") rescue nil)
            end
          end
        rescue Exception
        end
        ret = pbPriority_chrooked_stampede_orig(*args)
        bumped.each { |m, base| (m.instance_variable_set(:@priority, base) rescue nil) }
        ret
      end
    end
  end
  $chrooked_stampede_priority_installed = true
  ($chrooked_log.call("[chrooked:stampede] priority hook installed on PokeBattle_Battle") rescue nil)
end

# --- Hook (b): arm on KO, consume on contact move ---------------------------
# Via the compat shim's install_after_move (16.2 pbEffectsAfterHit / IF2
# pbEffectsAfterMove), normalized to one (user, target, move) call per target.
def chrooked_install_stampede_arm
  return if $chrooked_stampede_arm_installed
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_stampede_arm_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_stampede_arm_apply(user, target, thismove)
        begin
          return unless user && (user.hasWorkingAbility(:STAMPEDE) rescue false)
          was_armed = (user.instance_variable_get(:@chrooked_stampede_armed) rescue false)
          contact = (Chrooked.contact_move?(thismove) rescue false)
          if was_armed && contact
            user.instance_variable_set(:@chrooked_stampede_armed, false)
            ($chrooked_log.call("[chrooked:stampede] OBS event=consume contact=true") rescue nil)
          end
          fainted = target && (target.fainted? rescue (target.isFainted? rescue false))
          if fainted
            user.instance_variable_set(:@chrooked_stampede_armed, true)
            ($chrooked_log.call("[chrooked:stampede] OBS event=ko armed=true") rescue nil)
          end
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_after_move("chrooked_stampede_arm_apply", "pbAfterMove_chrooked_stampede_orig")
  $chrooked_stampede_arm_installed = true
  ($chrooked_log.call("[chrooked:stampede] arm hook installed (after-move seam)") rescue nil)
end

# --- Hook (c): clear the flag on switch-in ----------------------------------
# Via the compat shim's install_switch_in (16.2 pbAbilitiesOnSwitchIn / IF2
# pbEffectsOnSwitchIn); apply receives the switched-in flag.
def chrooked_install_stampede_reset
  return if $chrooked_stampede_reset_installed
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_stampede_reset_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_stampede_reset_apply(switched_in)
        begin
          return unless switched_in
          @chrooked_stampede_armed = false
          ($chrooked_log.call("[chrooked:stampede] OBS event=switchin reset=armed") rescue nil)
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_switch_in("chrooked_stampede_reset_apply", "pbSwitchIn_chrooked_stampede_orig")
  $chrooked_stampede_reset_installed = true
  ($chrooked_log.call("[chrooked:stampede] reset hook installed (switch-in seam)") rescue nil)
end

chrooked_install_stampede_priority if defined?(PokeBattle_Battle) &&
  PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbPriority")
chrooked_install_stampede_arm if defined?(PokeBattle_Battler) && defined?(Chrooked)
chrooked_install_stampede_reset if defined?(PokeBattle_Battler) && defined?(Chrooked)

if (!$chrooked_stampede_priority_installed || !$chrooked_stampede_arm_installed || !$chrooked_stampede_reset_installed) && defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_stampede_orig)
      alias_method :update_chrooked_stampede_orig, :update
      def update
        chrooked_install_stampede_priority if !$chrooked_stampede_priority_installed && defined?(PokeBattle_Battle)
        chrooked_install_stampede_arm if !$chrooked_stampede_arm_installed && defined?(PokeBattle_Battler)
        chrooked_install_stampede_reset if !$chrooked_stampede_reset_installed && defined?(PokeBattle_Battler)
        update_chrooked_stampede_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:stampede] deferred install armed on Graphics.update") rescue nil)
elsif !defined?(Graphics) && (!$chrooked_stampede_priority_installed || !$chrooked_stampede_arm_installed || !$chrooked_stampede_reset_installed)
  ($chrooked_log.call("[chrooked:stampede] ERROR: PokeBattle classes/Graphics missing at load") rescue nil)
end
