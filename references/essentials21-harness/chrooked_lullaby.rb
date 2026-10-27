# chrooked:lullaby
# ---------------------------------------------------------------------------
# Ruleset ability "lullaby": the holder's damaging sound moves have a 30% chance to
# make the target drowsy (Yawn's effect: asleep at the end of the next turn unless
# it switches).
#
# HAND-WRITTEN (mjolnir batch, 2026-10-26). Seam Battle::AbilityEffects::OnDealingHit,
# which Nova fires after a hit that dealt damage and missed any substitute: a
# soundMove? that is damagingMove?, the target not already drowsy
# (effects[PBEffects::Yawn] > 0), with no status, able to sleep (pbCanSleep?:
# Insomnia, Vital Spirit, Sweet Veil, Electric Terrain, Safeguard, Uproar), and
# not shielded from additional effects (Covert Cloak, Shield Dust: Poison Touch's
# gates), then a flat 30% (never doubled by Serene Grace, by decision) sets
# effects[PBEffects::Yawn] = 2 as the move Yawn does
# (003_Move/007_MoveEffects_BattlerOther.rb:67).
#     [chrooked:lullaby] OBS ability=true move=<ID> drowsy=true
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
  ChrookedLog.line("[chrooked:lullaby] load prior_on_dealing_hit=#{!Battle::AbilityEffects::OnDealingHit[:LULLABY].nil?}")
  Battle::AbilityEffects::OnDealingHit.add(:LULLABY,
    proc { |ability, user, target, move, battle|
      next if !move.soundMove? || !move.damagingMove?
      next if target.fainted? || target.damageState.substitute
      next if target.effects[PBEffects::Yawn] > 0 || target.status != :NONE
      next if !target.affectedByAdditionalEffects?
      next if target.hasActiveAbility?(:SHIELDDUST) && !target.beingMoldBroken?
      next if !target.pbCanSleep?(user, false, move)
      next if battle.pbRandom(100) >= 30
      battle.pbShowAbilitySplash(user)
      target.effects[PBEffects::Yawn] = 2
      battle.pbDisplay(_INTL("{1} made {2} drowsy!", user.pbThis, target.pbThis(true)))
      battle.pbHideAbilitySplash(user)
      ChrookedLog.line("[chrooked:lullaby] OBS ability=true move=#{move.id} drowsy=true")
    }
  )
  # The holder lands move_id on the foe n times (fixed seed), the foe's drowsiness
  # reset each time unless `drowsy`, with the status and ability asked: how many
  # hits left it drowsy.
  chrooked_lullaby_rolls = lambda do |t, spec, move_id: :HYPERVOICE, foe_ability: nil, foe_status: :NONE,
                                         drowsy: false, substitute: false, n: 400|
    b, holder, foe = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    foe.ability = foe_ability
    foe.status = foe_status
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    srand(t::SEED)
    count = 0
    n.times do
      foe.effects[PBEffects::Yawn] = drowsy ? 1 : 0
      foe.damageState.reset
      foe.damageState.substitute = substitute
      foe.damageState.hpLost = foe.damageState.calcDamage = 10
      Battle::AbilityEffects.triggerOnDealingHit(holder.ability, holder, foe, move, b)
      count += 1 if !drowsy && foe.effects[PBEffects::Yawn] == 2
      count += 1 if drowsy && foe.effects[PBEffects::Yawn] != 1
    end
    [count, n]
  end
  chrooked_lullaby_rate = lambda do |t, res, expected|
    count, n = res
    "rate=#{format('%.3f', count.to_f / n)} expected=#{expected} ok=#{t.rate_ok?(count, n, expected)}"
  end
  ($chrooked_selftest_cases ||= {})["lullaby"] = {
    ability: :LULLABY, control: nil, user: :WIGGLYTUFF, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["hyper_voice", ->(t, spec) {
        chrooked_lullaby_rate.call(t, chrooked_lullaby_rolls.call(t, spec), 0.3)
      }],
      ["not_sound", ->(t, spec) {
        tackle = chrooked_lullaby_rolls.call(t, spec, move_id: :TACKLE)
        sing = chrooked_lullaby_rolls.call(t, spec, move_id: :SING)
        "tackle_count=#{tackle[0]} sing_count=#{sing[0]} never=#{tackle[0] + sing[0] == 0}"
      }],
      ["already", ->(t, spec) {
        drowsy = chrooked_lullaby_rolls.call(t, spec, drowsy: true)
        statused = chrooked_lullaby_rolls.call(t, spec, foe_status: :PARALYSIS)
        "drowsy_changed=#{drowsy[0]} statused_count=#{statused[0]} never=#{drowsy[0] + statused[0] == 0}"
      }],
      ["cannot_sleep", ->(t, spec) {
        insomnia = chrooked_lullaby_rolls.call(t, spec, foe_ability: :INSOMNIA)
        vital = chrooked_lullaby_rolls.call(t, spec, foe_ability: :VITALSPIRIT)
        "insomnia_count=#{insomnia[0]} vital_spirit_count=#{vital[0]} never=#{insomnia[0] + vital[0] == 0}"
      }],
      ["substitute", ->(t, spec) {
        sub = chrooked_lullaby_rolls.call(t, spec, substitute: true)
        "substitute_count=#{sub[0]} never=#{sub[0] == 0}"
      }]
    ],
    without: [],
    fight: [:HYPERVOICE]
  }
  ChrookedLog.line("[chrooked:lullaby] installed on OnDealingHit")
rescue StandardError => e
  ChrookedLog.error("[chrooked:lullaby] ERROR #{e.class}: #{e.message}")
end
