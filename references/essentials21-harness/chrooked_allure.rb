# chrooked:allure
# ---------------------------------------------------------------------------
# Ruleset ability "allure": infatuation caused by the holder ignores gender, and a
# foe in love with the holder that hits it has its higher attacking stat lowered.
#
# HAND-WRITTEN (mjolnir batch, 2026-10-26). Two Seams:
#   - Battle::Battler#pbCanAttract?(user, showMessages) (002_Battler/004_Battler_Statuses.rb:522)
#     wrapped by alias_method with a `method_defined?` guard, as unattainable wraps
#     hasActiveAbility?: when `user` (the seducer) has Allure active, the gender test
#     is left out and every other gate kept (already infatuated, Aroma Veil or
#     Oblivious on the target, Aroma Veil on its allies, mold-breaking). Attract and
#     Destiny Knot both route through it, so the bypass covers every infatuation
#     the holder is the attractor of. No other harness file wraps pbCanAttract?.
#   - OnBeingHit: Nova fires it after a hit that dealt damage and missed any
#     substitute. If the attacker's Attract points at the holder, its higher
#     attacking stat (raw stat x stage, ties to Attack) is lowered one stage by
#     pbLowerStatStageByAbility, so Clear Body, Mist, Mirror Armor and a Substitute
#     answer as they do to Gooey.
#   No contact-roll infatuation: that is Cute Charm / Unattainable.
#     [chrooked:allure] OBS ability=true move=<ID> stat=<ATTACK|SPECIAL_ATTACK> lowered=<bool>
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
  ChrookedLog.line("[chrooked:allure] load prior_handler=#{!Battle::AbilityEffects::OnBeingHit[:ALLURE].nil?}")
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_allure_pbCanAttract?)
      alias_method :chrooked_allure_pbCanAttract?, :pbCanAttract?
      # Nova's body with the gender test left out; re-sync if Nova adds a gate.
      def pbCanAttract?(user, showMessages = true)
        return chrooked_allure_pbCanAttract?(user, showMessages) if !user || !user.hasActiveAbility?(:ALLURE)
        return false if fainted? || user.fainted?
        if @effects[PBEffects::Attract] >= 0
          @battle.pbDisplay(_INTL("{1} is unaffected!", pbThis)) if showMessages
          return false
        end
        if hasActiveAbility?([:AROMAVEIL, :OBLIVIOUS]) && !beingMoldBroken?
          if showMessages
            @battle.pbShowAbilitySplash(self)
            if Battle::Scene::USE_ABILITY_SPLASH
              @battle.pbDisplay(_INTL("{1} is unaffected!", pbThis))
            else
              @battle.pbDisplay(_INTL("{1} {2} prevents romance!", pbOfThis, abilityName))
            end
            @battle.pbHideAbilitySplash(self)
          end
          return false
        end
        allAllies.each do |b|
          next if !b.hasActiveAbility?(:AROMAVEIL) || b.beingMoldBroken?
          if showMessages
            @battle.pbShowAbilitySplash(b)
            if Battle::Scene::USE_ABILITY_SPLASH
              @battle.pbDisplay(_INTL("{1} is unaffected!", pbThis))
            else
              @battle.pbDisplay(_INTL("{1} {2} prevents romance!", b.pbOfThis, b.abilityName))
            end
            @battle.pbHideAbilitySplash(b)
          end
          return false
        end
        return true
      end
    end
  end
  # The attacker's higher attacking stat after stages; ties go to Attack.
  chrooked_allure_higher_stat = lambda do |battler|
    mults = Battle::Battler::STAT_STAGE_MULTIPLIERS
    divs  = Battle::Battler::STAT_STAGE_DIVISORS
    atk_stage = battler.stages[:ATTACK] + 6
    spa_stage = battler.stages[:SPECIAL_ATTACK] + 6
    atk = battler.attack * mults[atk_stage] / divs[atk_stage]
    spa = battler.spatk * mults[spa_stage] / divs[spa_stage]
    spa > atk ? :SPECIAL_ATTACK : :ATTACK
  end
  Battle::AbilityEffects::OnBeingHit.add(:ALLURE,
    proc { |ability, user, target, move, battle|
      next if target.fainted? || !user || user.fainted?
      next if target.damageState.substitute
      next if user.effects[PBEffects::Attract] != target.index
      stat = chrooked_allure_higher_stat.call(user)
      lowered = user.pbLowerStatStageByAbility(stat, 1, target)
      ChrookedLog.line("[chrooked:allure] OBS ability=true move=#{move.id} stat=#{stat} lowered=#{lowered}")
    }
  )
  # A 1v1 with the holder at index 1 and the foe at 0: genders as asked (0 male,
  # 1 female, nil leaves the species' own), the holder's ability on or off.
  chrooked_allure_pair = lambda do |t, spec, foe_species: :NIDORINO, holder_gender: nil, with_ability: true|
    foe_mon = t.mon(foe_species, [:TACKLE])
    holder_mon = t.mon(spec[:user], [:ATTRACT])
    holder_mon.gender = holder_gender unless holder_gender.nil?
    b = t.battle(foe_mon, holder_mon)
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    foe, holder = b.battlers[0], b.battlers[1]
    foe.ability = nil
    holder.ability = with_ability ? spec[:ability] : nil
    [b, foe, holder]
  end
  # The foe, in love with the holder (or not), lands one 10-HP Tackle on it with
  # the stages given: the foe's stage changes.
  chrooked_allure_hit = lambda do |t, spec, atk_stage: 0, spa_stage: 0, in_love: true, tie: false, prefix: ""|
    b, foe, holder = chrooked_allure_pair.call(t, spec)
    foe.spatk = foe.attack if tie
    foe.stages[:ATTACK] = atk_stage
    foe.stages[:SPECIAL_ATTACK] = spa_stage
    foe.effects[PBEffects::Attract] = in_love ? holder.index : -1
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:TACKLE))
    holder.damageState.reset
    holder.damageState.hpLost = holder.damageState.calcDamage = 10
    Battle::AbilityEffects.triggerOnBeingHit(holder.ability, foe, holder, move, b)
    "#{prefix}atk_change=#{foe.stages[:ATTACK] - atk_stage} #{prefix}spa_change=#{foe.stages[:SPECIAL_ATTACK] - spa_stage}"
  end
  ($chrooked_selftest_cases ||= {})["allure"] = {
    ability: :ALLURE, control: nil, user: :SKITTY, foe: :NIDORINO, neutral: true,
    calc: [],
    checks: [
      ["genderless", ->(t, spec) {
        _b, foe, holder = chrooked_allure_pair.call(t, spec, foe_species: :MAGNEZONE)
        with = foe.pbCanAttract?(holder, false)
        _b, foe, holder = chrooked_allure_pair.call(t, spec, foe_species: :MAGNEZONE, with_ability: false)
        without = foe.pbCanAttract?(holder, false)
        "can_attract=#{with} without_ability=#{without}"
      }],
      ["same_gender", ->(t, spec) {
        _b, foe, holder = chrooked_allure_pair.call(t, spec, holder_gender: 0)   # Nidorino is male
        with = foe.pbCanAttract?(holder, false)
        _b, foe, holder = chrooked_allure_pair.call(t, spec, holder_gender: 0, with_ability: false)
        without = foe.pbCanAttract?(holder, false)
        "can_attract=#{with} without_ability=#{without} foe_gender=#{foe.gender} holder_gender=#{holder.gender}"
      }],
      ["oblivious_aroma_veil", ->(t, spec) {
        _b, foe, holder = chrooked_allure_pair.call(t, spec, foe_species: :MAGNEZONE)
        foe.ability = :OBLIVIOUS
        oblivious = foe.pbCanAttract?(holder, false)
        foe.ability = :AROMAVEIL
        aroma = foe.pbCanAttract?(holder, false)
        foe.ability = nil
        foe.effects[PBEffects::Attract] = holder.index
        already = foe.pbCanAttract?(holder, false)
        "oblivious=#{oblivious} aroma_veil=#{aroma} already=#{already} never=#{!oblivious && !aroma && !already}"
      }],
      ["spa_higher", ->(t, spec) {
        loved = chrooked_allure_hit.call(t, spec, spa_stage: 2)
        unloved = chrooked_allure_hit.call(t, spec, spa_stage: 2, in_love: false, prefix: "unloved_")
        "#{loved} #{unloved}"
      }],
      ["tie_attack", ->(t, spec) {
        chrooked_allure_hit.call(t, spec, tie: true)
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:allure] installed: OnBeingHit, pbCanAttract? wrapped")
rescue StandardError => e
  ChrookedLog.error("[chrooked:allure] ERROR #{e.class}: #{e.message}")
end
