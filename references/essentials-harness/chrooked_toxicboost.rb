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
#         opponent); Chrooked.move_physical?(self, movetype).
#
# RESIDUAL IMMUNITY (precise) — PokeBattle_Battle#pbEndOfRoundPhase poison MASK.
#   The end-of-turn poison chip block is gated on `i.status==PBStatuses::POISON`.
#   So instead of skipping pbReduceHP (which can't tell the poison chip apart from
#   same-window sandstorm/Leech-Seed damage by amount), we MASK: before _orig, for
#   each TOXICBOOST holder that is poisoned, stash [status,statusCount] and set 0;
#   after _orig, restore. The poison block sees no poison and skips it, while
#   sandstorm (type-gated) and Leech Seed (effect-gated) STILL hit normally — the
#   earlier "skips other end-of-round self-damage" ceiling is gone. Same clear/
#   restore round-trip the overworld field hook below already uses.
#   Ceiling (narrow, intended): a TOXICBOOST + Hydration mon in rain won't have its
#   poison cured end-of-round (the cure also reads status) — consistent with the
#   ability wanting to KEEP poison for its boost.
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
        movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
        is_phys = (Chrooked.move_physical?(self, movetype) rescue false)
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

# --- Hook 2: mask poison across end-of-round so only the poison chip is skipped

def chrooked_install_toxicboost_eormask
  return if $chrooked_toxicboost_eormask_installed
  return unless defined?(PokeBattle_Battle)
  return unless PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")
  PokeBattle_Battle.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEndOfRoundPhase_chrooked_toxicboost_orig")
      alias_method :pbEndOfRoundPhase_chrooked_toxicboost_orig, :pbEndOfRoundPhase
      def pbEndOfRoundPhase(*args)
        masked = []
        begin
          @battlers.each do |b|
            next if b.nil?
            if (b.hasWorkingAbility(:TOXICBOOST) rescue false) &&
               (b.status == PBStatuses::POISON rescue false)
              masked.push([b, b.status, b.statusCount])
              b.status = 0
              b.statusCount = 0
              ($chrooked_log.call("[chrooked:toxicboost] OBS event=eor_mask ability=true effect=poison_chip SKIPPED") rescue nil)
            end
          end
        rescue Exception
        end
        begin
          ret = pbEndOfRoundPhase_chrooked_toxicboost_orig(*args)
        ensure
          masked.each do |b, st, sc|
            begin
              next if b.isFainted?   # fainted in EOR (e.g. sandstorm); leave reset
              b.status = st
              b.statusCount = sc
            rescue Exception
            end
          end
        end
        ret
      end
    end
  end
  $chrooked_toxicboost_eormask_installed = true
  ($chrooked_log.call("[chrooked:toxicboost] installed pbEndOfRoundPhase poison-mask on PokeBattle_Battle") rescue nil)
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
chrooked_install_toxicboost_eormask if defined?(PokeBattle_Battle) &&
  PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")
chrooked_install_toxicboost_field if defined?(Events) && Events.respond_to?(:onStepTakenTransferPossible)

if (defined?($chrooked_toxicboost_damage_installed) && $chrooked_toxicboost_damage_installed) &&
   (defined?($chrooked_toxicboost_eormask_installed) && $chrooked_toxicboost_eormask_installed) &&
   (defined?($chrooked_toxicboost_field_installed) && $chrooked_toxicboost_field_installed)
  # all installed eagerly
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_toxicboost_orig)
      alias_method :update_chrooked_toxicboost_orig, :update
      def update
        chrooked_install_toxicboost_damage if !$chrooked_toxicboost_damage_installed && defined?(PokeBattle_Move)
        chrooked_install_toxicboost_eormask if !$chrooked_toxicboost_eormask_installed && defined?(PokeBattle_Battle)
        chrooked_install_toxicboost_field if !$chrooked_toxicboost_field_installed && defined?(Events) && Events.respond_to?(:onStepTakenTransferPossible)
        update_chrooked_toxicboost_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:toxicboost] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:toxicboost] ERROR: PokeBattle classes/Graphics missing at load") rescue nil)
end
