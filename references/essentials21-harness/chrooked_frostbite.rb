# chrooked:frostbite
# ---------------------------------------------------------------------------
# Ruleset behavior "frostbite" (a status; mjolnir NV-12, Chris's decision
# 2026-10-22: bring the Ruleset's frostbite to Nova). A RESKIN of freeze, as the
# spec itself prescribes: the engine keeps :FROZEN (saves, items, Ice-type
# immunity, the freeze clause, every move that freezes all keep working), and only
# its behavior and text change. Every freeze in Nova is now frostbite.
#
#   1. Special damage is halved, unless the holder has Guts or Quick Feet: a wrapper
#      on Battle::Move#pbCalcDamageMultipliersStatusConditions, where Nova halves
#      burn's physical damage.
#   2. 1/16 of max HP at the end of each round, skipped by the Magic Guard family
#      (takesIndirectDamage?): a wrapper on Battle#pbEORStatusProblemDamage that runs
#      right after Nova's burn chip, with the same gates.
#   3. It never costs a turn and never randomly thaws: Battle::Battler#pbTryUseMove
#      runs with @status cleared (the ivar, not the setter, whose side effects touch
#      Truant and Toxic) so its freeze branch is skipped, then restored in an ensure.
#      The same goes for the multi-hit cut-off (pbUseMove_StopPerformingHits?) and
#      the AI's can_attack?, which otherwise treat the holder as unable to act.
#   4. Any Fire-type move the holder uses cures it (Chris, 2026-10-22: "any fire
#      move"), and so does a move that thaws its user (Nova's ThawsUser: Scald,
#      Steam Eruption...), as before. A wrapper on pbUseMove_CureUserStatus, which
#      pbUseMove calls right after setting move.calcType, so the type is the one the
#      move is used with (Weather Ball in sun, a Normal move turned Fire by Immolate).
# Text: being afflicted, the end-of-round chip, the cure, the self-cure and the
# status's name say frostbite.
#
# Kept from Nova as found (the spec says nothing): a hit by a Fire move still cures
# the target (pbEffectsAfterMove); harsh sun still prevents it; Ice types are
# immune; Ice Heal, Aspear Berry and every full cure cure it; its catch-rate bonus;
# the status icon graphic (still FRZ); Pursuit still skips a frostbitten pursuer;
# the rarely shown "already frozen" / "cannot be frozen" / "prevents freezing"
# lines of pbCanInflictStatus.
#
# Install, load order, the marker-gated oracle and the self-test registration at
# the end: references/essentials21-harness/README.md. The behavior cases (turn,
# damage, chip) are measured by the lab self-test and logged on this mechanic's
# behalf with source=selftest.
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
  ChrookedLog.line("[chrooked:frostbite] load prior=#{Battle::Battler.method_defined?(:chrooked_frostbite_pbTryUseMove)}")

  # class_eval, not `class ... end`: reopening a class this game lacks would quietly
  # create an empty one; class_eval raises instead, and the rescue logs it.
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_frostbite_pbTryUseMove)
      # 3. No turn skip and no random thaw.
      alias_method :chrooked_frostbite_pbTryUseMove, :pbTryUseMove
      def pbTryUseMove(choice, move, specialUsage, skipStatusFailureChecks)
        return chrooked_frostbite_pbTryUseMove(choice, move, specialUsage, skipStatusFailureChecks) if @status != :FROZEN
        @status = :NONE
        begin
          chrooked_frostbite_pbTryUseMove(choice, move, specialUsage, skipStatusFailureChecks)
        ensure
          @status = :FROZEN if @status == :NONE
        end
      end

      alias_method :chrooked_frostbite_pbUseMove_StopPerformingHits?, :pbUseMove_StopPerformingHits?
      def pbUseMove_StopPerformingHits?(move, user, targets)
        frozen = user.status == :FROZEN
        user.instance_variable_set(:@status, :NONE) if frozen
        chrooked_frostbite_pbUseMove_StopPerformingHits?(move, user, targets)
      ensure
        user.instance_variable_set(:@status, :FROZEN) if frozen && user.status == :NONE
      end

      # Text.
      alias_method :chrooked_frostbite_pbInflictStatus, :pbInflictStatus
      def pbInflictStatus(newStatus, newStatusCount = 0, msg = nil, user = nil)
        msg = _INTL("{1} was frostbitten!", pbThis) if newStatus == :FROZEN && (msg.nil? || msg.empty?)
        chrooked_frostbite_pbInflictStatus(newStatus, newStatusCount, msg, user)
      end

      alias_method :chrooked_frostbite_pbContinueStatus, :pbContinueStatus
      def pbContinueStatus(&block)
        return chrooked_frostbite_pbContinueStatus(&block) if self.status != :FROZEN
        anim_name = GameData::Status.get(:FROZEN).animation
        @battle.pbCommonAnimation(anim_name, self) if anim_name
        yield if block_given?
        @battle.pbDisplay(_INTL("{1} was hurt by its frostbite!", pbThis))
      end

      alias_method :chrooked_frostbite_pbCureStatus, :pbCureStatus
      def pbCureStatus(showMessages = true)
        return chrooked_frostbite_pbCureStatus(showMessages) if self.status != :FROZEN || !showMessages
        chrooked_frostbite_pbCureStatus(false)
        @battle.pbDisplay(_INTL("{1}'s frostbite was healed.", pbThis))
      end

      # 4. Any Fire-type move cures it, as does a move that thaws its user.
      alias_method :chrooked_frostbite_pbUseMove_CureUserStatus, :pbUseMove_CureUserStatus
      def pbUseMove_CureUserStatus(move)
        if @status == :FROZEN && (move.calcType == :FIRE || move.thawsUser?)
          pbCureStatus(false)
          @battle.pbDisplay(_INTL("{1}'s attack healed its frostbite!", pbThis))
        end
        chrooked_frostbite_pbUseMove_CureUserStatus(move)
      end
    end
  end

  # 1. Special damage halved (Guts and Quick Feet exempt), beside burn's physical halving.
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_frostbite_pbCalcDamageMultipliersStatusConditions)
      alias_method :chrooked_frostbite_pbCalcDamageMultipliersStatusConditions, :pbCalcDamageMultipliersStatusConditions
      def pbCalcDamageMultipliersStatusConditions(user, target, numTargets, type, baseDmg, multipliers)
        chrooked_frostbite_pbCalcDamageMultipliersStatusConditions(user, target, numTargets, type, baseDmg, multipliers)
        if user.status == :FROZEN && specialMove? && !user.hasActiveAbility?([:GUTS, :QUICKFEET])
          multipliers[:final_damage_multiplier] /= 2
        end
      end
    end
  end

  # 2. 1/16 chip at the end of each round, right after burn's, with burn's gates.
  Battle.class_eval do
    unless method_defined?(:chrooked_frostbite_pbEORStatusProblemDamage)
      alias_method :chrooked_frostbite_pbEORStatusProblemDamage, :pbEORStatusProblemDamage
      def pbEORStatusProblemDamage(priority)
        chrooked_frostbite_pbEORStatusProblemDamage(priority)
        priority.each do |battler|
          next if battler.fainted?
          next if battler.status != :FROZEN || !battler.takesIndirectDamage?
          battler.droppedBelowHalfHP = false
          dmg = battler.totalhp / 16
          battler.pbContinueStatus { battler.pbReduceHP(dmg, false) }
          battler.pbItemHPHealCheck
          battler.pbAbilitiesOnDamageTaken
          battler.pbFaint if battler.fainted?
          battler.droppedBelowHalfHP = false
        end
      end
    end
  end

  # 3, for the AI: a frostbitten battler can still attack.
  Battle::AI::AIBattler.class_eval do
    unless method_defined?(:chrooked_frostbite_can_attack?)
      alias_method :chrooked_frostbite_can_attack?, :can_attack?
      def can_attack?
        b = battler
        frozen = b.status == :FROZEN
        b.instance_variable_set(:@status, :NONE) if frozen
        chrooked_frostbite_can_attack?
      ensure
        b.instance_variable_set(:@status, :FROZEN) if frozen && b.status == :NONE
      end
    end
  end

  # The status's name, wherever the game shows it.
  GameData::Status.get(:FROZEN).instance_variable_set(:@real_name, "Frostbite")

  ($chrooked_selftest_cases ||= {})["frostbite"] = {
    ability: nil, user: :NUMEL, foe: :SNORLAX, neutral: true, status: :FROZEN,
    turn: [[:TACKLE, 50]],
    status_damage: [[:SURF, nil], [:TACKLE, nil], [:SURF, :GUTS], [:SURF, :QUICKFEET]],
    chip: [nil, :MAGICGUARD],
    cure: [:EMBER, :FLAMEWHEEL, :SCALD, :TACKLE],
    immune: [[:ICE], [:NORMAL]],
    calc: [], without: [], fight: []
  }
  ChrookedLog.line("[chrooked:frostbite] installed on pbTryUseMove, pbUseMove_StopPerformingHits?, " \
                   "status text, pbCalcDamageMultipliersStatusConditions, pbEORStatusProblemDamage, AI can_attack?")
rescue StandardError => e
  ChrookedLog.error("[chrooked:frostbite] ERROR #{e.class}: #{e.message}")
end
