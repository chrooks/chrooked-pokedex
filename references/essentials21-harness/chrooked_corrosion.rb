# chrooked:corrosion
# ---------------------------------------------------------------------------
# Ruleset behavior "corrosion": the game's own Corrosion (it can poison Steel and
# Poison types), and its Poison-type moves are super effective against Steel: the
# Steel slot counts x2, the other slot by the chart.
#
# HAND-WRITTEN (mjolnir NV-30). Nova's status clause is by name and stays. The new
# clause wraps Battle::Move#pbCalcTypeModSingle, the one type slot at a time Nova
# multiplies together: Poison into a Steel slot is x2 when the user holds Corrosion,
# so it is the holder's own moves only and the type chart itself is untouched.
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
  ChrookedLog.line("[chrooked:corrosion] load prior_wrapper=" \
                   "#{Battle::Move.method_defined?(:chrooked_corrosion_pbCalcTypeModSingle)}")
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_corrosion_pbCalcTypeModSingle)
      alias_method :chrooked_corrosion_pbCalcTypeModSingle, :pbCalcTypeModSingle
      def pbCalcTypeModSingle(moveType, defType, user, target)
        if moveType == :POISON && defType == :STEEL && user.respond_to?(:hasActiveAbility?) &&
           user.hasActiveAbility?(:CORROSION)
          return Effectiveness::SUPER_EFFECTIVE_MULTIPLIER
        end
        chrooked_corrosion_pbCalcTypeModSingle(moveType, defType, user, target)
      end
    end
  end
  # move_id by the holder (or a Pokemon with no ability) into a species: the type
  # multiplier Nova's pbCalcTypeMod gives, as a factor of neutral.
  chrooked_corrosion_into = lambda do |t, spec, move_id, species, ability = spec[:ability]|
    b = t.battle(t.mon(spec[:user], [move_id]), t.mon(species, [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    holder, target = b.battlers[0], b.battlers[1]
    holder.ability = ability
    target.ability = nil
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(holder)
    factor = move.pbCalcTypeMod(move.calcType, holder, target) / Effectiveness::NORMAL_EFFECTIVE_MULTIPLIER
    "move=#{move_id} target=#{species} factor=#{format('%.2f', factor)}"
  end
  ($chrooked_selftest_cases ||= {})["corrosion"] = {
    ability: :CORROSION, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: false,
    calc: [],
    checks: [
      ["steelix", ->(t, spec) { chrooked_corrosion_into.call(t, spec, :POISONJAB, :STEELIX) }],
      ["registeel", ->(t, spec) { chrooked_corrosion_into.call(t, spec, :GUNKSHOT, :REGISTEEL) }],
      ["scizor", ->(t, spec) { chrooked_corrosion_into.call(t, spec, :GASTRICSNARE, :SCIZOR) }],
      ["without", ->(t, spec) { chrooked_corrosion_into.call(t, spec, :POISONJAB, :REGISTEEL, nil) }],
      ["toxic", ->(t, spec) {
        b = t.battle(t.mon(spec[:user], [:TOXIC]), t.mon(:REGISTEEL, [:TACKLE]))
        b.pbCreateBattler(0, b.pbParty(0)[0], 0)
        b.pbCreateBattler(1, b.pbParty(1)[0], 0)
        holder, target = b.battlers[0], b.battlers[1]
        holder.ability = spec[:ability]
        target.ability = nil
        can = target.pbCanPoison?(holder, false)
        target.pbPoison(holder, nil, true) if can
        "can_poison=#{can} status=#{target.status} toxic=#{target.statusCount > 0}"
      }],
      ["razor_leaf", ->(t, spec) { chrooked_corrosion_into.call(t, spec, :RAZORLEAF, :REGISTEEL) }]
    ],
    without: [],
    fight: [:POISONJAB, :GUNKSHOT]
  }
  ChrookedLog.line("[chrooked:corrosion] installed on Battle::Move#pbCalcTypeModSingle")
rescue StandardError => e
  ChrookedLog.error("[chrooked:corrosion] ERROR #{e.class}: #{e.message}")
end
