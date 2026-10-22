# chrooked:infernalmaw
# ---------------------------------------------------------------------------
# Ruleset behavior "infernalmaw", three effects (mjolnir NV-11):
#   1. Biting moves deal 30% more damage.
#   2. Biting moves gain a 30% chance to burn the target.
#   3. Biting moves gain a flat 30% chance to make the target flinch.
# (The spec's summary for 2 still says 20%; its effect text, test case and a dated
# note say the burn was raised to 30% on 2026-06-30, so the port uses 30%.)
#
# HAND-WRITTEN: a template generates exactly one effect, and this spec has three.
#
# Effect 1, Seam Battle::AbilityEffects::DamageCalcFromUser: Nova's Strong Jaw
# (mults[:power_multiplier] *= 1.5 if move.bitingMove?) at 1.3x.
#
# Effects 2 and 3, Seam Battle::AbilityEffects::OnDealingHit, which Nova fires for
# the user's ability only after a hit that dealt damage and missed any substitute.
# Shaped like Nova's Poison Touch: no effect on a target unaffected by additional
# effects or holding Shield Dust (as for Stench and King's Rock too). The burn
# checks pbCanBurn? before its roll (Fire types, Water Veil, an existing status,
# Safeguard...), so a burn-immune target still takes the flinch roll. The flinch
# uses the normal helper, pbFlinch, which Inner Focus blocks; it rolls on its own,
# independent of the burn and of the move's own flinch chance.
#
# Install, load order, the marker-gated oracle, the OBS/EST split and the
# self-test registration at the end: references/essentials21-harness/README.md.
#     [chrooked:infernalmaw] OBS move=<ID> ability=true category=<Biting|none> result=<BOOSTED|NORMAL>   a hit's damage
#     [chrooked:infernalmaw] OBS move=<ID> ability=true hit=true can_burn=<bool> burned=<bool> flinched=<bool>   after a biting hit
# The chance cases (many rolls, rates checked) are measured by the lab self-test
# and logged on this mechanic's behalf with source=selftest.
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
  chrooked_table = Battle::AbilityEffects::DamageCalcFromUser
  ChrookedLog.line("[chrooked:infernalmaw] load prior_handler=#{!chrooked_table[:INFERNALMAW].nil?} " \
                   "prior_on_hit=#{!Battle::AbilityEffects::OnDealingHit[:INFERNALMAW].nil?}")
  chrooked_table.add(:INFERNALMAW,
    proc { |ability, user, target, move, mults, power, type|
      biting = move.bitingMove?
      mults[:power_multiplier] *= 1.3 if biting
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:infernalmaw] #{tag} move=#{move.id} ability=true " \
                         "category=#{biting ? 'Biting' : 'none'} result=#{biting ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  Battle::AbilityEffects::OnDealingHit.add(:INFERNALMAW,
    proc { |ability, user, target, move, battle|
      next if !move.bitingMove?
      next if !target.affectedByAdditionalEffects?
      next if target.hasActiveAbility?(:SHIELDDUST) && !target.beingMoldBroken?
      can_burn = target.pbCanBurn?(user, false)
      burned = false
      if can_burn && battle.pbRandom(100) < 30
        battle.pbShowAbilitySplash(user)
        msg = nil
        if !Battle::Scene::USE_ABILITY_SPLASH
          msg = _INTL("{1}'s {2} burned {3}!", user.pbThis, user.abilityName, target.pbThis(true))
        end
        target.pbBurn(user, msg)
        battle.pbHideAbilitySplash(user)
        burned = true
      end
      flinched = battle.pbRandom(100) < 30
      target.pbFlinch(user) if flinched
      ChrookedLog.line("[chrooked:infernalmaw] OBS move=#{move.id} ability=true hit=true " \
                       "can_burn=#{can_burn} burned=#{burned} flinched=#{flinched}")
    }
  )
  ($chrooked_selftest_cases ||= {})["infernalmaw"] = {
    ability: :INFERNALMAW, control: :STRONGJAW, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:CRUNCH, 1.0], [:TACKLE, 1.0]],
    chance: [
      [:CRUNCH, {status: :BURN, status_rate: 0.3, flinch_rate: 0.3}],
      [:TACKLE, {status: :BURN, status_rate: 0, flinch_rate: 0}],
      [:CRUNCH, {status: :BURN, status_rate: 0, flinch_rate: 0.3, setup: {target_types: [:FIRE]}}]
    ],
    without: [],
    fight: [:CRUNCH, :TACKLE]
  }
  ChrookedLog.line("[chrooked:infernalmaw] installed on DamageCalcFromUser and OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:infernalmaw] ERROR #{e.class}: #{e.message}")
end
