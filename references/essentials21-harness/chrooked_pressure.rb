# chrooked:pressure
# ---------------------------------------------------------------------------
# Ruleset behavior "pressure": the game's own Pressure (a foe's move aimed at it costs
# an extra PP; its entry announcement), and on entry every adjacent foe loses its
# positive stat stages; negative ones stay.
#
# HAND-WRITTEN (mjolnir NV-28). The PP cost stays Nova's (pbUseMove_RemoveExtraPP asks
# hasActiveAbility?(:PRESSURE)). OnSwitchIn keeps Nova's own handler, called first for
# its announcement, then resets each near foe's raised stages to 0, one message per foe
# it changed, nothing for a foe with no boost.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:pressure] OBS ability=true entry=true reset=<n>   each entry
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
  chrooked_pressure_own = Battle::AbilityEffects::OnSwitchIn[:PRESSURE]
  # Nova's GameData::Stat.each_battle yields and returns no enumerator, so collect it.
  chrooked_pressure_stats = []
  GameData::Stat.each_battle { |s| chrooked_pressure_stats << s.id }
  ChrookedLog.line("[chrooked:pressure] load prior_handler=#{!chrooked_pressure_own.nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:PRESSURE,
    proc { |ability, battler, battle, switch_in|
      chrooked_pressure_own&.call(ability, battler, battle, switch_in)
      reset = 0
      battle.allOtherSideBattlers(battler.index).each do |b|
        next if !b.near?(battler)
        raised = chrooked_pressure_stats.select { |s| b.stages[s] > 0 }
        next if raised.empty?
        raised.each { |s| b.stages[s] = 0 }
        battle.pbDisplay(_INTL("{1}'s stat boosts were nullified by the pressure!", b.pbThis))
        reset += 1
      end
      ChrookedLog.line("[chrooked:pressure] OBS ability=true entry=true reset=#{reset}")
    }
  )
  ($chrooked_selftest_cases ||= {})["pressure"] = {
    ability: :PRESSURE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["mixed", ->(t, spec) {
        b, holder, foe = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        foe.stages[:ATTACK] = 2
        foe.stages[:SPEED] = -1
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        "foe_attack=#{foe.stages[:ATTACK]} foe_speed=#{foe.stages[:SPEED]}"
      }],
      ["doubles", ->(t, spec) {
        b, holder, _ally, foe, foe2 = t.doubles(spec)
        holder.ability = spec[:ability]
        foe.stages[:ATTACK] = 2
        foe2.stages[:SPECIAL_ATTACK] = 1
        foe2.stages[:EVASION] = 1
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        boosted = [foe, foe2].sum { |x| chrooked_pressure_stats.count { |s| x.stages[s] > 0 } }
        "boosts_left=#{boosted}"
      }],
      ["no_boosts", ->(t, spec) {
        b, holder, foe = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        foe.stages[:SPEED] = -1
        before = foe.stages.dup
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        "changed=#{foe.stages != before}"
      }],
      ["pp", ->(t, spec) {
        b, holder, foe = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        move = foe.moves[0]
        pp = move.pp
        foe.pbReducePP(move)                                   # the move's own PP
        foe.send(:pbUseMove_RemoveExtraPP, move, foe, [holder])   # Nova's Pressure
        "pp_used=#{pp - move.pp}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:pressure] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:pressure] ERROR #{e.class}: #{e.message}")
end
