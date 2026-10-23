# chrooked:daydreamer
# ---------------------------------------------------------------------------
# Ruleset behavior "daydreamer": its moves that need a sleeping target (Dream Eater,
# Nightmare) work on one awake, and a foe's Nightmare keeps hurting while awake as
# long as the holder is on the field against it.
#
# HAND-WRITTEN (mjolnir NV-31).
#   - Dream Eater (HealUserByHalfOfDamageDoneIfTargetAsleep) and Nightmare
#     (StartDamageTargetEachTurnIfTargetAsleep): their pbFailsAgainstTarget? skip the
#     asleep test for the holder's use, every other test kept. The target stays awake;
#     moves that put to sleep, and Snore and Sleep Talk (the user's own sleep), are
#     untouched.
#   - Battle#pbEOREffectDamage clears Nightmare from an awake battler before dealing
#     it; for an awake battler with Nightmare facing an active holder, the wrapper puts
#     the effect back after and deals Nova's 1/4 with its message. With no holder
#     there, Nova clears it as before.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md. Its checks measure it.
# ---------------------------------------------------------------------------

unless defined?(ChrookedLog)
  module ChrookedLog
    # Resolved once, at load, while the working directory is the game folder.
    LOG     = File.expand_path("chrooked_load.log")
    ENABLED = File.exist?(File.expand_path("chrooked-oracle.on"))

    def self.line(msg)
      write(msg) if ENABLED
    end

    def self.error(msg)
      write(msg)
    end

    def self.write(msg)
      File.open(LOG, "a") { |f| f.puts(msg) }
    rescue StandardError
      nil
    end
  end
end

begin
  ChrookedLog.line("[chrooked:daydreamer] load prior_wrapper=" \
                   "#{Battle.method_defined?(:chrooked_daydreamer_pbEOREffectDamage)}")
  Battle::Move::HealUserByHalfOfDamageDoneIfTargetAsleep.class_eval do
    unless method_defined?(:chrooked_daydreamer_pbFailsAgainstTarget?)
      alias_method :chrooked_daydreamer_pbFailsAgainstTarget?, :pbFailsAgainstTarget?
      def pbFailsAgainstTarget?(user, target, show_message)
        return false if user.hasActiveAbility?(:DAYDREAMER)   # its only test is the target's sleep
        chrooked_daydreamer_pbFailsAgainstTarget?(user, target, show_message)
      end
    end
  end
  Battle::Move::StartDamageTargetEachTurnIfTargetAsleep.class_eval do
    unless method_defined?(:chrooked_daydreamer_pbFailsAgainstTarget?)
      alias_method :chrooked_daydreamer_pbFailsAgainstTarget?, :pbFailsAgainstTarget?
      def pbFailsAgainstTarget?(user, target, show_message)
        return chrooked_daydreamer_pbFailsAgainstTarget?(user, target, show_message) if !user.hasActiveAbility?(:DAYDREAMER)
        if target.effects[PBEffects::Nightmare]   # Nova's other test, kept
          @battle.pbDisplay(_INTL("But it failed!")) if show_message
          return true
        end
        false
      end
    end
  end
  Battle.class_eval do
    unless method_defined?(:chrooked_daydreamer_pbEOREffectDamage)
      alias_method :chrooked_daydreamer_pbEOREffectDamage, :pbEOREffectDamage
      def pbEOREffectDamage(priority)
        dreaming = priority.select do |b|
          b.effects[PBEffects::Nightmare] && !b.asleep? && !b.fainted? &&
            allOtherSideBattlers(b.index).any? { |o| o.hasActiveAbility?(:DAYDREAMER) }
        end
        chrooked_daydreamer_pbEOREffectDamage(priority)
        dreaming.each do |b|
          b.effects[PBEffects::Nightmare] = true
          next if b.fainted? || !b.takesIndirectDamage?
          pbCommonAnimation("Nightmare", b)
          b.pbTakeEffectDamage(b.totalhp / 4) { |_hp_lost| pbDisplay(_INTL("{1} is locked in a nightmare!", b.pbThis)) }
        end
      end
    end
  end
  # The user (holder, or not) aims move_id at the awake foe: whether it fails.
  chrooked_daydreamer_aim = lambda do |t, spec, move_id, ability = spec[:ability]|
    b, user, foe = t.pair(spec, move_id)
    user.ability = ability
    move = user.moves[0]
    !!move.pbFailsAgainstTarget?(user, foe, false)
  end
  ($chrooked_selftest_cases ||= {})["daydreamer"] = {
    ability: :DAYDREAMER, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["dream_eater", ->(t, spec) {
        b, user, foe = t.pair(spec, :DREAMEATER)
        user.ability = spec[:ability]
        user.hp = 1
        move = user.moves[0]
        fails = !!move.pbFailsAgainstTarget?(user, foe, false)
        foe.damageState.reset
        foe.damageState.hpLost = 40
        move.pbEffectAgainstTarget(user, foe)
        "fails=#{fails} healed=#{user.hp - 1}"
      }],
      ["nightmare", ->(t, spec) {
        b, holder, foe = t.pair(spec, :NIGHTMARE)
        holder.ability = spec[:ability]
        move = holder.moves[0]
        fails = !!move.pbFailsAgainstTarget?(holder, foe, false)
        move.pbEffectAgainstTarget(holder, foe) if !fails
        hp = foe.hp
        b.send(:pbEOREffectDamage, [holder, foe])
        "fails=#{fails} nightmare=#{foe.effects[PBEffects::Nightmare]} lost=#{hp - foe.hp} " \
        "quarter_lost=#{hp - foe.hp == foe.totalhp / 4}"
      }],
      ["holder_gone", ->(t, spec) {
        b, holder, foe = t.pair(spec, :NIGHTMARE)
        holder.ability = spec[:ability]
        foe.effects[PBEffects::Nightmare] = true
        holder.hp = 0   # fainted or switched out: no Daydreamer on the field
        hp = foe.hp
        b.send(:pbEOREffectDamage, [foe])
        "nightmare=#{foe.effects[PBEffects::Nightmare]} lost=#{hp - foe.hp}"
      }],
      ["hypnosis_yawn", ->(t, spec) {
        "hypnosis_fails=#{chrooked_daydreamer_aim.call(t, spec, :HYPNOSIS)} " \
        "yawn_fails=#{chrooked_daydreamer_aim.call(t, spec, :YAWN)}"
      }],
      ["snore_sleep_talk", ->(t, spec) {
        b, user, _foe = t.pair(spec, :SNORE)
        user.ability = spec[:ability]
        snore = user.moves[0]
        "snore_usable_awake=#{!snore.pbMoveFailed?(user, [])}"
      }],
      ["ally_without", ->(t, spec) { "dream_eater_fails=#{chrooked_daydreamer_aim.call(t, spec, :DREAMEATER, nil)}" }]
    ],
    without: [],
    fight: [:DREAMEATER, :NIGHTMARE]
  }
  ChrookedLog.line("[chrooked:daydreamer] installed on Dream Eater, Nightmare and Battle#pbEOREffectDamage")
rescue StandardError => e
  ChrookedLog.error("[chrooked:daydreamer] ERROR #{e.class}: #{e.message}")
end
