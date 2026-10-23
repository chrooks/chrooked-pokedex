# chrooked:nematocyst
# ---------------------------------------------------------------------------
# Ruleset behavior "nematocyst": its Water moves have a 30% chance to badly poison, and
# every poison it inflicts is bad poison.
#
# HAND-WRITTEN (mjolnir NV-30).
#   - OnDealingHit, Poison Touch's shape: after a damaging hit with a Water move (as
#     used), on a target not spared additional effects (Shield Dust, Covert Cloak), a
#     30% roll, then pbCanPoison? (so Poison and Steel types, Immunity and an existing
#     status refuse it) and bad poison.
#   - Battle::Battler#pbPoison: a poison whose source holds Nematocyst is bad poison,
#     whatever inflicts it (Poison Sting, Toxic Spikes it laid, Poison Point).
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
  ChrookedLog.line("[chrooked:nematocyst] load prior_handler=" \
                   "#{!Battle::AbilityEffects::OnDealingHit[:NEMATOCYST].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:NEMATOCYST,
    proc { |ability, user, target, move, battle|
      next if move.calcType != :WATER
      next if !target.affectedByAdditionalEffects?
      next if target.hasActiveAbility?(:SHIELDDUST) && !target.beingMoldBroken?
      next if battle.pbRandom(100) >= 30
      next if !target.pbCanPoison?(user, false)
      battle.pbShowAbilitySplash(user)
      target.pbPoison(user, nil, true)
      battle.pbHideAbilitySplash(user)
    }
  )
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_nematocyst_pbPoison)
      alias_method :chrooked_nematocyst_pbPoison, :pbPoison
      def pbPoison(user = nil, msg = nil, toxic = false)
        toxic = true if user.respond_to?(:hasActiveAbility?) && user.hasActiveAbility?(:NEMATOCYST)
        chrooked_nematocyst_pbPoison(user, msg, toxic)
      end
    end
  end
  # The holder's move into a species n times (fixed seed), the target's status reset
  # each time: how often it was poisoned, and how often badly.
  chrooked_nematocyst_rolls = lambda do |t, spec, move_id, species, n: 400|
    b = t.battle(t.mon(spec[:user], [move_id]), t.mon(species, [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    holder, target = b.battlers[0], b.battlers[1]
    holder.ability = spec[:ability]
    target.ability = nil
    move = holder.moves[0]
    move.calcType = move.pbCalcType(holder)
    srand(t::SEED)
    poisoned = toxic = 0
    n.times do
      target.status = :NONE
      target.damageState.reset
      Battle::AbilityEffects.triggerOnDealingHit(holder.ability, holder, target, move, b)
      chance = move.pbAdditionalEffectChance(holder, target)
      move.pbAdditionalEffect(holder, target) if chance > 0 && b.pbRandom(100) < chance
      next if target.status != :POISON
      poisoned += 1
      toxic += 1 if target.statusCount > 0
    end
    [poisoned, toxic, n]
  end
  ($chrooked_selftest_cases ||= {})["nematocyst"] = {
    ability: :NEMATOCYST, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: false,
    calc: [],
    checks: [
      ["surf_chansey", ->(t, spec) {
        poisoned, toxic, n = chrooked_nematocyst_rolls.call(t, spec, :SURF, :CHANSEY)
        "rate=#{format('%.3f', poisoned.to_f / n)} ok=#{t.rate_ok?(poisoned, n, 0.3)} all_toxic=#{toxic == poisoned}"
      }],
      ["poison_sting", ->(t, spec) {
        poisoned, toxic, n = chrooked_nematocyst_rolls.call(t, spec, :POISONSTING, :SNORLAX)
        "poisoned=#{poisoned} toxic=#{toxic} all_toxic=#{poisoned > 0 && toxic == poisoned} n=#{n}"
      }],
      ["surf_toxapex", ->(t, spec) {
        poisoned, _toxic, n = chrooked_nematocyst_rolls.call(t, spec, :SURF, :TOXAPEX)
        "poisoned=#{poisoned} n=#{n}"
      }]
    ],
    without: [],
    fight: [:SURF, :POISONSTING]
  }
  ChrookedLog.line("[chrooked:nematocyst] installed on OnDealingHit and Battler#pbPoison")
rescue StandardError => e
  ChrookedLog.error("[chrooked:nematocyst] ERROR #{e.class}: #{e.message}")
end
