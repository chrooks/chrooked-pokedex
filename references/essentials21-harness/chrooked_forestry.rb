# chrooked:forestry
# ---------------------------------------------------------------------------
# Ruleset behavior "forestry": All of this Pokemon's attacks deal 30% more damage
# while Grassy Terrain is up.
#
# HAND-WRITTEN (mjolnir NV-9) to prove a field-gated boost on a real engine before
# it becomes the conditional_boost template. Essentials 21 Seam:
# Battle::AbilityEffects::DamageCalcFromUser. The gate is Nova's own test for
# Grassy Terrain's healing (@field.terrain == :Grassy && battler.affectedByTerrain?),
# which is false while the user is airborne (Flying type, Levitate, Magnet Rise...)
# or semi-invulnerable. The boost is a power multiplier, as Nova's Sand Force (the
# vanilla field-gated 1.3x: mults[:power_multiplier] *= 1.3 in a sandstorm).
# Translated from references/rejuv-harness/chrooked_forestry.rb (Grassy field and
# not airborne -> 1.3x final damage).
#
# Install, load order, the marker-gated oracle, the OBS/EST split and the
# self-test registration at the end: references/essentials21-harness/README.md.
#     [chrooked:forestry] OBS move=<ID> ability=true terrain=<TERRAIN> grounded=<true|false> result=<BOOSTED|NORMAL>   a real hit
#     [chrooked:forestry] EST ...   an AI estimate, never scored
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
  ChrookedLog.line("[chrooked:forestry] load prior_handler=#{!chrooked_table[:FORESTRY].nil?}")
  chrooked_table.add(:FORESTRY,
    proc { |ability, user, target, move, mults, power, type|
      terrain  = user.battle.field.terrain
      grounded = user.affectedByTerrain?
      boosted  = terrain == :Grassy && grounded
      mults[:power_multiplier] *= 1.3 if boosted
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:forestry] #{tag} move=#{move.id} ability=true terrain=#{terrain} " \
                         "grounded=#{grounded} result=#{boosted ? 'BOOSTED' : 'NORMAL'}")
      end
    }
  )
  ($chrooked_selftest_cases ||= {})["forestry"] = {
    ability: :FORESTRY, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [[:TACKLE, 1.0, {terrain: :Grassy}], [:TACKLE, 1.0, {}], [:TACKLE, 1.0, {terrain: :Grassy, airborne: true}]],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:forestry] installed on Battle::AbilityEffects::DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:forestry] ERROR #{e.class}: #{e.message}")
end
