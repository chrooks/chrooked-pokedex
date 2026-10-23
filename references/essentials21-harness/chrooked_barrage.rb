# chrooked:barrage
# ---------------------------------------------------------------------------
# Ruleset behavior "barrage": its pulse moves never miss, and its single-target pulse
# moves hit all adjacent foes.
#
# HAND-WRITTEN (mjolnir NV-29). No Guard and Amplifier's spread, for pulse moves.
#   - AccuracyCalcFromUser: base accuracy 0 for a pulse move (pulseMove?), which
#     pbAccuracyCheck takes as a certain hit, as No Guard's handler sets it; evasion and
#     accuracy stages never come into it. Semi-invulnerable turns still block it.
#   - Battle::Move#pbTarget: for the holder, a damaging pulse move that targets one foe
#     targets all near foes instead (as chrooked_amplifier.rb does for sound moves).
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
  ChrookedLog.line("[chrooked:barrage] load prior_handler=" \
                   "#{!Battle::AbilityEffects::AccuracyCalcFromUser[:BARRAGE].nil?}")
  Battle::AbilityEffects::AccuracyCalcFromUser.add(:BARRAGE,
    proc { |ability, mods, user, target, move, type|
      mods[:base_accuracy] = 0 if move.pulseMove?
    }
  )
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_barrage_pbTarget)
      alias_method :chrooked_barrage_pbTarget, :pbTarget
      def pbTarget(user)
        target = chrooked_barrage_pbTarget(user)
        return target if !pulseMove? || !damagingMove? || !target.can_target_one_foe?
        return target if !user.respond_to?(:hasActiveAbility?) || !user.hasActiveAbility?(:BARRAGE)
        GameData::Target.get(:AllNearFoes)
      end
    end
  end
  # Doubles: the holder's move into a foe at +6 evasion; its target kind and whether
  # Nova's accuracy check lets it hit, 30 times with a fixed seed.
  chrooked_barrage_volley = lambda do |t, spec, move_id|
    b, holder, _ally, foe, _foe2 = t.doubles(spec, [move_id])
    holder.ability = spec[:ability]
    foe.stages[:EVASION] = 6
    move = holder.moves[0]
    move.calcType = move.pbCalcType(holder)
    srand(t::SEED)
    hits = 30.times.count { move.pbAccuracyCheck(holder, foe) }
    "move=#{move_id} target=#{move.pbTarget(holder).id} hits=#{hits} never_misses=#{hits == 30}"
  end
  ($chrooked_selftest_cases ||= {})["barrage"] = {
    ability: :BARRAGE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["water_pulse", ->(t, spec) { chrooked_barrage_volley.call(t, spec, :WATERPULSE) }],
      # The case names Hydro Pump as the move that is not a pulse move; the Ruleset marks
      # Hydro Pump a pulse move (flags: [pulse]), so Fire Blast, 85 accuracy, stands in.
      ["not_pulse", ->(t, spec) { chrooked_barrage_volley.call(t, spec, :FIREBLAST) }]
    ],
    without: [],
    fight: [:WATERPULSE, :FIREBLAST]
  }
  ChrookedLog.line("[chrooked:barrage] installed on AccuracyCalcFromUser and Battle::Move#pbTarget")
rescue StandardError => e
  ChrookedLog.error("[chrooked:barrage] ERROR #{e.class}: #{e.message}")
end
