# chrooked:toxicboost
# ---------------------------------------------------------------------------
# Toxic Boost: while the user is poisoned, its physical moves deal x1.5 damage.
# (Mainline canon boosts the +50% Attack stat; this fork applies it as a flat
# 1.5x physical-damage modifier — same shape as the Flare Boost special clone.)
#
# Single verified Seam (Ruby 1.8: alias_method chaining, NO prepend/TracePoint;
# call _orig first; deferred install on Graphics.update):
#
#   DAMAGE — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent).
#     `attacker` is the user; returns the multiplier in 0x1000 units. We multiply
#     the _orig result by 1.5 (rounded) when:
#       - attacker.hasWorkingAbility(:TOXICBOOST), AND
#       - attacker.status == PBStatuses::POISON (regular OR bad/toxic poison both
#         report PBStatuses::POISON), AND
#       - the move's resolved type is physical: movetype = pbType(@type, attacker,
#         opponent); pbIsPhysical?(movetype).
#
# RESIDUAL IMMUNITY (now ported) — PokeBattle_Battler#pbReduceHP(amt,anim,registerDamage).
#   The end-of-turn poison chip is applied in PokeBattle_Battle#pbEndOfRoundPhase
#   (verified line ~3599) via i.pbReduceHP, gated only on !MAGICGUARD. We override
#   pbReduceHP and return 0 (no damage) when the holder has TOXICBOOST, is poisoned,
#   AND the call originates from pbEndOfRoundPhase (checked via `caller`). The caller
#   scope is what makes this safe: a normal move/recoil hit does NOT match, so only
#   the poison residual is skipped. Fail-safe: if `caller` lacks method names on a
#   given build, the guard never fires and normal poison chip resumes (status quo),
#   never wrongly skipping other damage.
#
# No stateful per-battler ivar is used (live reads + caller scope), so no
# pbAbilitiesOnSwitchIn reset is needed.
#
# HARNESS (Route B log oracle): each gate firing logs one OBS line:
#     [chrooked:toxicboost] OBS move=<NAME> toxicboost=<bool> poison=<bool> phys=<bool> result=<BOOSTED|NORMAL>
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

# --- Hook: physical damage x1.5 while poisoned -----------------------------

def chrooked_install_toxicboost_damage
  return if $chrooked_toxicboost_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_toxicboost_orig")
      alias_method :pbModifyDamage_chrooked_toxicboost_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_toxicboost_orig(damagemult, attacker, opponent)
        is_tb = (attacker.hasWorkingAbility(:TOXICBOOST) rescue false)
        is_psn = (attacker.status == PBStatuses::POISON rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_phys = (pbIsPhysical?(movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_tb && is_psn && is_phys
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:toxicboost] OBS move=#{movename} toxicboost=#{is_tb} poison=#{is_psn} phys=#{is_phys} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:toxicboost] OBS move=#{movename} toxicboost=#{is_tb} poison=#{is_psn} phys=#{is_phys} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_toxicboost_damage_installed = true
  ($chrooked_log.call("[chrooked:toxicboost] installed pbModifyDamage on PokeBattle_Move") rescue nil)
end

# --- Hook 2: skip the end-of-turn poison residual --------------------------

def chrooked_install_toxicboost_residual
  return if $chrooked_toxicboost_residual_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbReduceHP")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbReduceHP_chrooked_toxicboost_orig")
      alias_method :pbReduceHP_chrooked_toxicboost_orig, :pbReduceHP
      def pbReduceHP(amt, anim = false, registerDamage = true)
        begin
          # ponytail: skip self-poison chip during end-of-round (flag set by the
          # pbEndOfRoundPhase wrapper, since mkxp Ruby 1.8 `caller` has no method
          # names). Ceiling: this also skips any OTHER end-of-round self-damage on a
          # poisoned TOXICBOOST holder (sandstorm/leech) in the rare overlap — fine.
          if $chrooked_toxicboost_in_eor &&
             (self.hasWorkingAbility(:TOXICBOOST) rescue false) &&
             (self.status == PBStatuses::POISON rescue false)
            ($chrooked_log.call("[chrooked:toxicboost] OBS event=residual ability=true effect=poison_chip SKIPPED") rescue nil)
            return 0
          end
        rescue Exception
        end
        pbReduceHP_chrooked_toxicboost_orig(amt, anim, registerDamage)
      end
    end
  end
  $chrooked_toxicboost_residual_installed = true
  ($chrooked_log.call("[chrooked:toxicboost] installed pbReduceHP on PokeBattle_Battler") rescue nil)
end

# --- Hook 3: mark the end-of-round window so Hook 2 knows the context --------

def chrooked_install_toxicboost_eorflag
  return if $chrooked_toxicboost_eorflag_installed
  return unless defined?(PokeBattle_Battle)
  return unless PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")
  PokeBattle_Battle.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEndOfRoundPhase_chrooked_toxicboost_orig")
      alias_method :pbEndOfRoundPhase_chrooked_toxicboost_orig, :pbEndOfRoundPhase
      def pbEndOfRoundPhase(*args)
        $chrooked_toxicboost_in_eor = true
        begin
          pbEndOfRoundPhase_chrooked_toxicboost_orig(*args)
        ensure
          $chrooked_toxicboost_in_eor = false
        end
      end
    end
  end
  $chrooked_toxicboost_eorflag_installed = true
  ($chrooked_log.call("[chrooked:toxicboost] installed pbEndOfRoundPhase flag on PokeBattle_Battle") rescue nil)
end

# --- Hook 4 (out-of-canon extra): PREVENT overworld walking poison ----------
# The field poison chip is a registered proc (PField_Field, Events.onStepTakenTransferPossible)
# whose exclusion is hardcoded to :IMMUNITY — no alias point. The callback Event stores its
# procs in @callbacks (push-only via +), but we can unshift ours to the FRONT. So: a front
# proc temporarily clears poison on TOXICBOOST holders (the engine proc then skips them — no
# red flash, no HP chip), and a back proc (appended, runs last) restores the status. This
# prevents rather than undoes, so no flash and no 1-HP edge.
# ponytail: status round-trips within one step's dispatch; other step handlers briefly see
# cleared status. None of them read poison status, so it's safe. Restore is rescue-guarded.
def chrooked_install_toxicboost_field
  return if $chrooked_toxicboost_field_installed
  return unless defined?(Events) && Events.respond_to?(:onStepTakenTransferPossible)
  ev = Events.onStepTakenTransferPossible
  clear_cb = proc { |_sender, _e|
    begin
      if $Trainer
        for i in $Trainer.party
          if i && i.status == PBStatuses::POISON && !i.isEgg? &&
             (isConst?(i.ability, PBAbilities, :TOXICBOOST) rescue false)
            i.instance_variable_set(:@chrooked_tb_psn, [i.status, i.statusCount])
            i.status = 0; i.statusCount = 0
            ($chrooked_log.call("[chrooked:toxicboost] OBS event=field ability=true effect=walk_poison PREVENTED") rescue nil)
          end
        end
      end
    rescue Exception
    end
  }
  restore_cb = proc { |_sender, _e|
    begin
      if $Trainer
        for i in $Trainer.party
          saved = (i.instance_variable_get(:@chrooked_tb_psn) rescue nil) if i
          if saved
            i.status = saved[0]; i.statusCount = saved[1]
            i.instance_variable_set(:@chrooked_tb_psn, nil)
          end
        end
      end
    rescue Exception
    end
  }
  begin
    ev.instance_variable_get(:@callbacks).unshift(clear_cb)   # run BEFORE the engine's poison proc
  rescue Exception
    ev += clear_cb   # fallback: at least appended (degrades to no-op prevent)
  end
  ev += restore_cb   # appended -> runs after the engine proc -> restores
  $chrooked_toxicboost_field_installed = true
  ($chrooked_log.call("[chrooked:toxicboost] installed field-poison PREVENT (clear/restore) on Events.onStepTakenTransferPossible") rescue nil)
end

# --- Install / deferred-install (all hooks) ---------------------------------

chrooked_install_toxicboost_damage if defined?(PokeBattle_Move) &&
  PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
chrooked_install_toxicboost_residual if defined?(PokeBattle_Battler) &&
  PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbReduceHP")
chrooked_install_toxicboost_eorflag if defined?(PokeBattle_Battle) &&
  PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")
chrooked_install_toxicboost_field if defined?(Events) && Events.respond_to?(:onStepTakenTransferPossible)

if (defined?($chrooked_toxicboost_damage_installed) && $chrooked_toxicboost_damage_installed) &&
   (defined?($chrooked_toxicboost_residual_installed) && $chrooked_toxicboost_residual_installed) &&
   (defined?($chrooked_toxicboost_eorflag_installed) && $chrooked_toxicboost_eorflag_installed) &&
   (defined?($chrooked_toxicboost_field_installed) && $chrooked_toxicboost_field_installed)
  # all installed eagerly
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_toxicboost_orig)
      alias_method :update_chrooked_toxicboost_orig, :update
      def update
        chrooked_install_toxicboost_damage if !$chrooked_toxicboost_damage_installed && defined?(PokeBattle_Move)
        chrooked_install_toxicboost_residual if !$chrooked_toxicboost_residual_installed && defined?(PokeBattle_Battler)
        chrooked_install_toxicboost_eorflag if !$chrooked_toxicboost_eorflag_installed && defined?(PokeBattle_Battle)
        chrooked_install_toxicboost_field if !$chrooked_toxicboost_field_installed && defined?(Events) && Events.respond_to?(:onStepTakenTransferPossible)
        update_chrooked_toxicboost_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:toxicboost] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:toxicboost] ERROR: PokeBattle classes/Graphics missing at load") rescue nil)
end
