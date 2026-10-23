# chrooked:deathgrip
# ---------------------------------------------------------------------------
# Ruleset behavior "deathgrip": contact moves have a 30% chance to trap the target.
#
# HAND-WRITTEN (mjolnir NV-22). Seam Battle::AbilityEffects::OnDealingHit, gated as
# Poison Touch. The trap is Bind's own (BindTarget): 5 or 6 rounds, TrappingMove
# :BIND so the round-end squeeze and its damage are Nova's, TrappingUser the holder,
# Bind's message. Never over an existing trap.
#     [chrooked:deathgrip] OBS ability=true move=<ID> contact=true trapped=<bool>   after a contact hit
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
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
  ChrookedLog.line("[chrooked:deathgrip] load prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:DEATHGRIP].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:DEATHGRIP,
    proc { |ability, user, target, move, battle|
      next if !move.pbContactMove?(user)
      next if target.fainted? || !target.affectedByAdditionalEffects?
      next if target.hasActiveAbility?(:SHIELDDUST) && !target.beingMoldBroken?
      next if target.effects[PBEffects::Trapping] > 0
      trapped = false
      if battle.pbRandom(100) < 30
        battle.pbShowAbilitySplash(user)
        target.effects[PBEffects::Trapping]     = 5 + battle.pbRandom(2)
        target.effects[PBEffects::TrappingMove] = :BIND
        target.effects[PBEffects::TrappingUser] = user.index
        battle.pbDisplay(_INTL("{1} was squeezed by {2}!", target.pbThis, user.pbThis(true)))
        battle.pbHideAbilitySplash(user)
        trapped = true
      end
      ChrookedLog.line("[chrooked:deathgrip] OBS ability=true move=#{move.id} contact=true trapped=#{trapped}")
    }
  )
  ($chrooked_selftest_cases ||= {})["deathgrip"] = {
    ability: :DEATHGRIP, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    hit_rolls: [[:TACKLE, {kind: :trap, rate: 0.3}], [:WATERGUN, {kind: :trap, rate: 0}],
                [:TACKLE, {kind: :trap, rate: 0, target_trapped: true}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:deathgrip] installed on OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:deathgrip] ERROR #{e.class}: #{e.message}")
end
