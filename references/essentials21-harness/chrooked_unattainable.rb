# chrooked:unattainable
# ---------------------------------------------------------------------------
# Ruleset ability "unattainable": its own Cute Charm without the gender check, plus
# Unaware (the Ruleset composes it as unattainable + unaware).
#
# HAND-WRITTEN WHOLE (mjolnir NV-28), as Thorned Succulent is (NV-26): an ability that
# lists itself cannot be a generated composition, so this file is the whole ability.
#   - its own part: OnBeingHit, Nova's Cute Charm handler with pbCanAttract?'s gender
#     test left out and every other gate kept: the holder survived, the move made
#     contact, no Protective Pads, the attacker not already infatuated, no Oblivious
#     or Aroma Veil on it or Aroma Veil on its allies (unless mold-broken), a 30% roll,
#     then Nova's pbAttract (Destiny Knot included). Nova fires OnBeingHit only after a
#     hit that dealt damage and missed any substitute;
#   - Unaware: Nova's damage calc asks hasActiveAbility?(:UNAWARE) by name, so the
#     holder answers yes to it; its accuracy handlers are copied.
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
  ChrookedLog.line("[chrooked:unattainable] load prior_handler=" \
                   "#{!Battle::AbilityEffects::OnBeingHit[:UNATTAINABLE].nil?}")
  Battle::AbilityEffects::OnBeingHit.add(:UNATTAINABLE,
    proc { |ability, user, target, move, battle|
      next if target.fainted? || !user || user.fainted?
      next if !move.pbContactMove?(user) || !user.affectedByContactEffect?
      next if user.effects[PBEffects::Attract] >= 0
      next if user.hasActiveAbility?([:AROMAVEIL, :OBLIVIOUS]) && !user.beingMoldBroken?
      next if user.allAllies.any? { |b| b.hasActiveAbility?(:AROMAVEIL) && !b.beingMoldBroken? }
      next if battle.pbRandom(100) >= 30
      battle.pbShowAbilitySplash(target)
      battle.pbCommonAnimation("Attract", user)
      msg = nil
      if !Battle::Scene::USE_ABILITY_SPLASH
        msg = _INTL("{1} {2} made {3} fall in love!", target.pbOfThis, target.abilityName, user.pbThis(true))
      end
      user.pbAttract(target, msg)
      battle.pbHideAbilitySplash(target)
    }
  )
  Battle::AbilityEffects::AccuracyCalcFromUser.copy(:UNAWARE, :UNATTAINABLE)
  Battle::AbilityEffects::AccuracyCalcFromTarget.copy(:UNAWARE, :UNATTAINABLE)
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_unattainable_hasActiveAbility?)
      alias_method :chrooked_unattainable_hasActiveAbility?, :hasActiveAbility?
      def hasActiveAbility?(check_ability, ignore_fainted = false)
        asked = check_ability.is_a?(Array) ? check_ability : [check_ability]
        if asked.include?(:UNAWARE) && chrooked_unattainable_hasActiveAbility?(:UNATTAINABLE, ignore_fainted)
          return true
        end
        chrooked_unattainable_hasActiveAbility?(check_ability, ignore_fainted)
      end
    end
  end
  # The attacker (species, ability, item, gender) hits the holder with move_id n times
  # (fixed seed), its infatuation cleared each time unless `already`: the share infatuated.
  chrooked_unattainable_rolls = lambda do |t, spec, attacker_species: :NIDORINO, move_id: :TACKLE, ability: nil,
                                           item: nil, already: false, n: 400|
    attacker_mon = t.mon(attacker_species, [move_id])
    holder_mon = t.mon(spec[:user], [:TACKLE])   # Nidoran (M) holds it; Nidorino is male too
    b = t.battle(attacker_mon, holder_mon)
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    attacker, holder = b.battlers[0], b.battlers[1]
    attacker.ability = ability
    attacker.item = item
    holder.ability = spec[:ability]
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    srand(t::SEED)
    count = 0
    n.times do
      attacker.effects[PBEffects::Attract] = already ? holder.index : -1
      holder.damageState.reset
      holder.damageState.hpLost = holder.damageState.calcDamage = 10
      Battle::AbilityEffects.triggerOnBeingHit(holder.ability, attacker, holder, move, b)
      count += 1 if !already && attacker.effects[PBEffects::Attract] >= 0
      count += 1 if already && attacker.effects[PBEffects::Attract] != holder.index
    end
    [count, n, attacker.gender, holder.gender]
  end
  chrooked_unattainable_rate = lambda do |t, res, expected|
    count, n, agender, hgender = res
    "rate=#{format('%.3f', count.to_f / n)} expected=#{expected} ok=#{t.rate_ok?(count, n, expected)} " \
    "attacker_gender=#{agender} holder_gender=#{hgender}"
  end
  ($chrooked_selftest_cases ||= {})["unattainable"] = {
    ability: :UNATTAINABLE, control: nil, user: :NIDORANmA, foe: :NIDORINO, neutral: true,
    calc: [],
    checks: [
      ["same_gender", ->(t, spec) {
        chrooked_unattainable_rate.call(t, chrooked_unattainable_rolls.call(t, spec), 0.3)
      }],
      ["genderless", ->(t, spec) {
        chrooked_unattainable_rate.call(t, chrooked_unattainable_rolls.call(t, spec, attacker_species: :MAGNEZONE), 0.3)
      }],
      ["oblivious_aroma_veil", ->(t, spec) {
        oblivious = chrooked_unattainable_rolls.call(t, spec, ability: :OBLIVIOUS)
        aroma = chrooked_unattainable_rolls.call(t, spec, ability: :AROMAVEIL)
        "oblivious_count=#{oblivious[0]} aroma_count=#{aroma[0]} never=#{oblivious[0] + aroma[0] == 0}"
      }],
      ["non_contact_pads", ->(t, spec) {
        water = chrooked_unattainable_rolls.call(t, spec, move_id: :WATERGUN)
        pads = chrooked_unattainable_rolls.call(t, spec, item: :PROTECTIVEPADS)
        "water_gun_count=#{water[0]} pads_count=#{pads[0]} never=#{water[0] + pads[0] == 0}"
      }],
      ["already", ->(t, spec) {
        res = chrooked_unattainable_rolls.call(t, spec, already: true)
        "changed=#{res[0]}"
      }],
      ["unaware", ->(t, spec) {
        b, foe, holder = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        foe.stages[:ATTACK] = 6
        boosted = t.hit(b, foe, holder, :TACKLE)
        foe.stages[:ATTACK] = 0
        plain = t.hit(b, foe, holder, :TACKLE)
        "boosted_foe_hit=#{boosted} plain_hit=#{plain} ignored=#{boosted == plain}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:unattainable] installed: OnBeingHit, Unaware copied and answered to")
rescue StandardError => e
  ChrookedLog.error("[chrooked:unattainable] ERROR #{e.class}: #{e.message}")
end
