# chrooked:vampiric
# ---------------------------------------------------------------------------
# Ruleset behavior "vampiric": contact moves drain a quarter of the damage dealt.
#
# HAND-WRITTEN (mjolnir NV-14) to prove a heal-on-hit before it becomes the
# hit_drain template. Seam Battle::AbilityEffects::OnDealingHit, which Nova fires
# for the user's ability only after a hit that dealt damage and missed any
# substitute. The heal goes through Nova's own drain path,
# Battle::Battler#pbRecoverHPFromDrain, as its drain moves do: Big Root adds 30%,
# Heal Block and full HP stop it, and a Liquid Ooze target reverses it. The amount
# is the HP the target lost on this hit / 4, rounded as Nova's drain moves round.
# Nothing happens, and nothing is said, when the user could not heal and the target
# has no Liquid Ooze, so a full-HP holder is not told its foe was drained every hit.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:vampiric] OBS move=<ID> ability=true contact=<bool> ooze=<bool> can_heal=<bool> hp_lost=<n> change=<n> result=<HEALED|REVERSED|NONE>   after a hit
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
  ChrookedLog.line("[chrooked:vampiric] load prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:VAMPIRIC].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:VAMPIRIC,
    proc { |ability, user, target, move, battle|
      gated    = move.pbContactMove?(user)
      ooze     = target.hasActiveAbility?(:LIQUIDOOZE, true)
      can_heal = user.canHeal?
      amount   = (target.damageState.hpLost / 4.0).round
      before   = user.hp
      if gated && amount > 0 && !user.fainted? && (can_heal || ooze)
        battle.pbShowAbilitySplash(user)
        user.pbRecoverHPFromDrain(amount, target)
        battle.pbHideAbilitySplash(user)
      end
      change = user.hp - before
      ChrookedLog.line("[chrooked:vampiric] OBS move=#{move.id} ability=true contact=#{move.pbContactMove?(user)} " \
                       "ooze=#{ooze} can_heal=#{can_heal} hp_lost=#{target.damageState.hpLost} change=#{change} " \
                       "result=#{change > 0 ? 'HEALED' : (change < 0 ? 'REVERSED' : 'NONE')}")
    }
  )
  ($chrooked_selftest_cases ||= {})["vampiric"] = {
    ability: :VAMPIRIC, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    drain: [[:TACKLE, {hp_lost: 100}], [:WATERGUN, {hp_lost: 100}],
            [:TACKLE, {hp_lost: 100, target_ability: :LIQUIDOOZE}]],
    without: [],
    fight: [:TACKLE, :WATERGUN]
  }
  ChrookedLog.line("[chrooked:vampiric] installed on OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:vampiric] ERROR #{e.class}: #{e.message}")
end
