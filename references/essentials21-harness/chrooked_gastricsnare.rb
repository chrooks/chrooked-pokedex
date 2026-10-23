# chrooked:gastricsnare
# ---------------------------------------------------------------------------
# Ruleset move "gastricsnare": always super effective against Bug types (the Bug slot
# counts x2, the other slot by the chart), with a 30% chance to poison.
#
# HAND-WRITTEN (mjolnir NV-30), a move, not an ability. Its Ruleset effect is its own
# (gastric-snare), so apply writes it with FunctionCode None and no effect chance;
# this port gives the move both halves, keyed on its id:
#   - Battle::Move#pbCalcTypeModSingle: a Bug slot is x2 for Gastric Snare, as Nova's
#     Freeze-Dry overrides Water's;
#   - Battle::Move#initialize and #pbAdditionalEffect: a 30% chance, rolled by Nova's
#     own additional-effect step (Serene Grace, Shield Dust, Covert Cloak and a
#     Substitute as for any move), to poison through pbCanPoison? and pbPoison, as
#     Nova's PoisonTarget does.
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
  ChrookedLog.line("[chrooked:gastricsnare] load move=#{GameData::Move.exists?(:GASTRICSNARE)}")
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_gastricsnare_pbCalcTypeModSingle)
      alias_method :chrooked_gastricsnare_pbCalcTypeModSingle, :pbCalcTypeModSingle
      def pbCalcTypeModSingle(moveType, defType, user, target)
        return Effectiveness::SUPER_EFFECTIVE_MULTIPLIER if @id == :GASTRICSNARE && defType == :BUG
        chrooked_gastricsnare_pbCalcTypeModSingle(moveType, defType, user, target)
      end

      # Nova reads @addlEffect itself, so the chance is set where the move is built.
      alias_method :chrooked_gastricsnare_initialize, :initialize
      def initialize(battle, move)
        chrooked_gastricsnare_initialize(battle, move)
        @addlEffect = 30 if @id == :GASTRICSNARE && @addlEffect.to_i == 0
      end

      alias_method :chrooked_gastricsnare_pbAdditionalEffect, :pbAdditionalEffect
      def pbAdditionalEffect(user, target)
        return chrooked_gastricsnare_pbAdditionalEffect(user, target) if @id != :GASTRICSNARE
        return if target.damageState.substitute
        target.pbPoison(user) if target.pbCanPoison?(user, false, self)
      end
    end
  end
  # Gastric Snare into a species: the type factor, and over 400 hits how often the
  # additional effect poisoned (the target's status reset each time unless `statused`).
  chrooked_gastricsnare_into = lambda do |t, spec, species, statused: false, n: 400|
    b = t.battle(t.mon(spec[:user], [:GASTRICSNARE]), t.mon(species, [:TACKLE]))
    b.pbCreateBattler(0, b.pbParty(0)[0], 0)
    b.pbCreateBattler(1, b.pbParty(1)[0], 0)
    user, target = b.battlers[0], b.battlers[1]
    user.ability = nil
    target.ability = nil
    move = user.moves[0]
    move.calcType = move.pbCalcType(user)
    factor = move.pbCalcTypeMod(move.calcType, user, target) / Effectiveness::NORMAL_EFFECTIVE_MULTIPLIER
    srand(t::SEED)
    poisoned = 0
    n.times do
      target.status = statused ? :PARALYSIS : :NONE
      target.damageState.reset
      chance = move.pbAdditionalEffectChance(user, target)
      move.pbAdditionalEffect(user, target) if chance > 0 && b.pbRandom(100) < chance
      poisoned += 1 if target.status == :POISON
    end
    "target=#{species} factor=#{format('%.2f', factor)} chance=#{move.addlEffect} " \
    "rate=#{format('%.3f', poisoned.to_f / n)} ok=#{t.rate_ok?(poisoned, n, statused ? 0 : 0.3)}"
  end
  ($chrooked_selftest_cases ||= {})["gastricsnare"] = {
    status: nil, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: false,
    calc: [],
    checks: [
      ["caterpie", ->(t, spec) { chrooked_gastricsnare_into.call(t, spec, :CATERPIE) }],
      ["scyther", ->(t, spec) { chrooked_gastricsnare_into.call(t, spec, :SCYTHER) }],
      ["kangaskhan", ->(t, spec) { chrooked_gastricsnare_into.call(t, spec, :KANGASKHAN) }],
      ["statused_bug", ->(t, spec) { chrooked_gastricsnare_into.call(t, spec, :CATERPIE, statused: true) }],
      ["scizor_corrosion", ->(t, spec) {
        b = t.battle(t.mon(spec[:user], [:GASTRICSNARE]), t.mon(:SCIZOR, [:TACKLE]))
        b.pbCreateBattler(0, b.pbParty(0)[0], 0)
        b.pbCreateBattler(1, b.pbParty(1)[0], 0)
        user, target = b.battlers[0], b.battlers[1]
        user.ability = :CORROSION
        target.ability = nil
        move = user.moves[0]
        move.calcType = move.pbCalcType(user)
        factor = move.pbCalcTypeMod(move.calcType, user, target) / Effectiveness::NORMAL_EFFECTIVE_MULTIPLIER
        "target=SCIZOR factor=#{format('%.2f', factor)}"
      }]
    ],
    without: [],
    fight: [:GASTRICSNARE]
  }
  ChrookedLog.line("[chrooked:gastricsnare] installed on Battle::Move (type, additional effect)")
rescue StandardError => e
  ChrookedLog.error("[chrooked:gastricsnare] ERROR #{e.class}: #{e.message}")
end
