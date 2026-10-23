# chrooked:deeprooted
# ---------------------------------------------------------------------------
# Ruleset behavior "deeprooted": HP it recovers from draining (drain moves, Leech Seed)
# is 1.3x, rounded down, at least 1.
#
# HAND-WRITTEN (mjolnir NV-30). Every drain in Nova goes through
# Battle::Battler#pbRecoverHPFromDrain, the drain moves and Leech Seed alike; for the
# holder the amount is x1.3 before Nova's own step, where Big Root adds its 1.3 on
# top. A Liquid Ooze target still reverses the drain, unscaled.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:deeprooted] OBS ability=true drain=<n> scaled=<n>   each drain it recovers
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
  ChrookedLog.line("[chrooked:deeprooted] load prior_wrapper=" \
                   "#{Battle::Battler.method_defined?(:chrooked_deeprooted_pbRecoverHPFromDrain)}")
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_deeprooted_pbRecoverHPFromDrain)
      alias_method :chrooked_deeprooted_pbRecoverHPFromDrain, :pbRecoverHPFromDrain
      def pbRecoverHPFromDrain(amt, target, msg = nil)
        if hasActiveAbility?(:DEEPROOTED) && amt > 0 && !target.hasActiveAbility?(:LIQUIDOOZE, true)
          scaled = [(amt * 1.3).floor, 1].max
          ChrookedLog.line("[chrooked:deeprooted] OBS ability=true drain=#{amt} scaled=#{scaled}")
          amt = scaled
        end
        chrooked_deeprooted_pbRecoverHPFromDrain(amt, target, msg)
      end
    end
  end
  # The holder at a low HP drains `amt` from the foe (or, for Tackle, hits it): its gain.
  chrooked_deeprooted_drain = lambda do |t, spec, amt|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    holder.hp = 1
    hp = holder.hp
    if amt
      holder.pbRecoverHPFromDrain(amt, foe)
    else
      tackle = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:TACKLE))
      foe.damageState.reset
      foe.damageState.hpLost = 20
      Battle::AbilityEffects.triggerOnDealingHit(holder.ability, holder, foe, tackle, b)
      tackle.pbEffectAfterAllHits(holder, foe)
    end
    "drained=#{amt || 'none'} recovered=#{holder.hp - hp}"
  end
  ($chrooked_selftest_cases ||= {})["deeprooted"] = {
    ability: :DEEPROOTED, control: nil, user: :SNORLAX, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["giga_drain", ->(t, spec) { chrooked_deeprooted_drain.call(t, spec, 50) }],
      # Leech Seed's end of round hands the seeder its drain through the same method.
      ["leech_seed", ->(t, spec) { chrooked_deeprooted_drain.call(t, spec, 10) }],
      ["tackle", ->(t, spec) { chrooked_deeprooted_drain.call(t, spec, nil) }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:deeprooted] installed on Battler#pbRecoverHPFromDrain")
rescue StandardError => e
  ChrookedLog.error("[chrooked:deeprooted] ERROR #{e.class}: #{e.message}")
end
