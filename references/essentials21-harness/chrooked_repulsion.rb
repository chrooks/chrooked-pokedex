# chrooked:repulsion
# ---------------------------------------------------------------------------
# Ruleset behavior "repulsion": on entry it rises with Magnet Rise for 5 turns.
#
# HAND-WRITTEN (mjolnir NV-26). Seam Battle::AbilityEffects::OnSwitchIn. It sets
# the same effects[PBEffects::MagnetRise] counter the move sets, with the move's own
# message, and fails where the move fails (Gravity, Ingrain, Smack Down, a Magnet Rise
# already up, which then keeps its own timer). Everything after is Nova's Magnet Rise:
# the countdown and its message at the end of each round, Smack Down, Thousand Arrows
# and Gravity ending it, the Ground immunity while airborne.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:repulsion] OBS ability=true entry=true rose=<bool>   each entry
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
  ChrookedLog.line("[chrooked:repulsion] load prior_handler=" \
                   "#{!Battle::AbilityEffects::OnSwitchIn[:REPULSION].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:REPULSION,
    proc { |ability, battler, battle, switch_in|
      rise = battle.field.effects[PBEffects::Gravity] == 0 && !battler.effects[PBEffects::Ingrain] &&
             !battler.effects[PBEffects::SmackDown] && battler.effects[PBEffects::MagnetRise] == 0
      if rise
        battle.pbShowAbilitySplash(battler)
        battler.effects[PBEffects::MagnetRise] = 5
        battle.pbDisplay(_INTL("{1} levitated with electromagnetism!", battler.pbThis))
        battle.pbHideAbilitySplash(battler)
      end
      ChrookedLog.line("[chrooked:repulsion] OBS ability=true entry=true rose=#{rise}")
    }
  )
  # The holder enters (Magnet Rise preset to `rising` first); then the foe's move.
  chrooked_repulsion_entry = lambda do |t, spec, rising|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    holder.effects[PBEffects::MagnetRise] = rising
    Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
    [b, holder, foe]
  end
  ($chrooked_selftest_cases ||= {})["repulsion"] = {
    ability: :REPULSION, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["earthquake", ->(t, spec) {
        b, holder, foe = chrooked_repulsion_entry.call(t, spec, 0)
        quake = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:EARTHQUAKE))
        quake.calcType = quake.pbCalcType(foe)
        type_mod = quake.pbCalcTypeMod(quake.calcType, foe, holder)
        # Nova's own airborne check, as the foe's move meets the holder (Magnet Rise's branch).
        immune = foe.pbSuccessCheckAgainstTarget_TargetImmunityByBeingAirborne?(quake, foe, holder, [holder],
                                                                                 type_mod, false)
        "magnet_rise=#{holder.effects[PBEffects::MagnetRise]} airborne=#{holder.airborne?} ground_immune=#{immune}"
      }],
      ["smack_down", ->(t, spec) {
        b, holder, foe = chrooked_repulsion_entry.call(t, spec, 0)
        smack = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:SMACKDOWN))
        holder.damageState.reset
        smack.pbEffectAfterAllHits(foe, holder)
        "magnet_rise=#{holder.effects[PBEffects::MagnetRise]} airborne=#{holder.airborne?}"
      }],
      ["already_rising", ->(t, spec) {
        _b, holder, _foe = chrooked_repulsion_entry.call(t, spec, 3)
        "magnet_rise=#{holder.effects[PBEffects::MagnetRise]}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:repulsion] installed on OnSwitchIn")
rescue StandardError => e
  ChrookedLog.error("[chrooked:repulsion] ERROR #{e.class}: #{e.message}")
end
