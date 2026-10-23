# chrooked:soulsight
# ---------------------------------------------------------------------------
# Ruleset behavior "soulsight": it cannot flinch, its Normal and Fighting moves hit
# Ghost types, and its special Fighting moves never miss.
#
# HAND-WRITTEN (mjolnir NV-30). Inner Focus's flinch block, Scrappy's Ghost clause and
# No Guard for one kind of move, each written for this ability alone (answering to
# Inner Focus or Scrappy by name would bring their Intimidate immunity too):
#   - Battle::Battler#pbFlinch: no flinch for the holder (Mold Breaker aside), as
#     Inner Focus's test in it;
#   - Battle::Move#pbCalcTypeModSingle: a Ghost slot that would make the holder's
#     Normal or Fighting move ineffective counts as neutral, as Scrappy's;
#   - AccuracyCalcFromUser: base accuracy 0 for a special Fighting move, a certain hit.
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
  ChrookedLog.line("[chrooked:soulsight] load prior_handler=" \
                   "#{!Battle::AbilityEffects::AccuracyCalcFromUser[:SOULSIGHT].nil?}")
  Battle::AbilityEffects::AccuracyCalcFromUser.add(:SOULSIGHT,
    proc { |ability, mods, user, target, move, type|
      mods[:base_accuracy] = 0 if type == :FIGHTING && move.specialMove?
    }
  )
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_soulsight_pbFlinch)
      alias_method :chrooked_soulsight_pbFlinch, :pbFlinch
      def pbFlinch(user = nil)
        return if hasActiveAbility?(:SOULSIGHT) && !beingMoldBroken?
        chrooked_soulsight_pbFlinch(user)
      end
    end
  end
  Battle::Move.class_eval do
    unless method_defined?(:chrooked_soulsight_pbCalcTypeModSingle)
      alias_method :chrooked_soulsight_pbCalcTypeModSingle, :pbCalcTypeModSingle
      def pbCalcTypeModSingle(moveType, defType, user, target)
        ret = chrooked_soulsight_pbCalcTypeModSingle(moveType, defType, user, target)
        if ret == Effectiveness::INEFFECTIVE_MULTIPLIER && defType == :GHOST && [:NORMAL, :FIGHTING].include?(moveType) &&
           user.respond_to?(:hasActiveAbility?) && user.hasActiveAbility?(:SOULSIGHT)
          return Effectiveness::NORMAL_EFFECTIVE_MULTIPLIER
        end
        ret
      end
    end
  end
  # The holder's move into a target (its accuracy stage, ability, weather and types set
  # first): the type factor, and how many of 30 accuracy checks hit (fixed seed).
  chrooked_soulsight_volley = lambda do |t, spec, move_id, accuracy: 0, target_ability: nil, weather: nil,
                                          target_types: nil|
    b, holder, target = t.pair(spec, move_id)
    holder.ability = spec[:ability]
    holder.stages[:ACCURACY] = accuracy
    target.ability = target_ability
    b.field.weather = weather if weather
    if target_types
      target.types = target_types
      target.effects[PBEffects::ExtraType] = nil
    end
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(holder)
    factor = move.pbCalcTypeMod(move.calcType, holder, target) / Effectiveness::NORMAL_EFFECTIVE_MULTIPLIER
    srand(t::SEED)
    hits = 30.times.count { move.pbAccuracyCheck(holder, target) }
    "move=#{move_id} factor=#{format('%.2f', factor)} hits=#{hits} never_misses=#{hits == 30}"
  end
  ($chrooked_selftest_cases ||= {})["soulsight"] = {
    ability: :SOULSIGHT, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["aura_sphere_sand_veil", ->(t, spec) {
        chrooked_soulsight_volley.call(t, spec, :AURASPHERE, accuracy: -6, target_ability: :SANDVEIL,
                                       weather: :Sandstorm)
      }],
      ["focus_blast", ->(t, spec) { chrooked_soulsight_volley.call(t, spec, :FOCUSBLAST) }],
      ["aura_sphere_ghost", ->(t, spec) {
        chrooked_soulsight_volley.call(t, spec, :AURASPHERE, target_types: [:GHOST])
      }],
      ["fake_out", ->(t, spec) {
        _b, holder, foe = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        holder.pbFlinch(foe)
        without = (holder.ability = nil; holder.pbFlinch(foe); holder.effects[PBEffects::Flinch])
        holder.effects[PBEffects::Flinch] = false
        holder.ability = spec[:ability]
        holder.pbFlinch(foe)
        "flinched=#{holder.effects[PBEffects::Flinch]} flinched_without=#{without}"
      }]
    ],
    without: [],
    fight: [:AURASPHERE, :FOCUSBLAST]
  }
  ChrookedLog.line("[chrooked:soulsight] installed on AccuracyCalcFromUser, Battler#pbFlinch and Move#pbCalcTypeModSingle")
rescue StandardError => e
  ChrookedLog.error("[chrooked:soulsight] ERROR #{e.class}: #{e.message}")
end
