# chrooked:phantom
# ---------------------------------------------------------------------------
# Ruleset behavior "phantom": on entry it gains Ghost as an added type, as if hit by
# Trick-or-Treat, unless it is already Ghost-type or cannot change type.
#
# HAND-WRITTEN (mjolnir NV-28).
#   - OnSwitchIn: effects[PBEffects::ExtraType] = :GHOST, the added-type slot
#     Trick-or-Treat and Forest's Curse write, under the splash with "Ghost type was
#     added to <holder>!". Nova's pbTypes(true) then counts it for matchups, STAB and
#     every pbHasType?; pbInitEffects clears it on switching (Baton Pass included).
#     Trick-or-Treat then fails (it is Ghost), and Forest's Curse writes Grass over it.
#   - The AI's switch scoring (Battle::AI#rate_replacement_pokemon) reads a party
#     Pokemon's own types; while it rates a Phantom holder, Pokemon#types adds Ghost,
#     so the foe's last move is weighed against the type it will have on entry.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:phantom] OBS ability=true entry=true added=<bool>   each entry
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

module ChrookedPhantom
  # The party Pokemon the AI is rating right now, when it has Phantom.
  def self.rating(pkmn)
    @rating = pkmn if pkmn.ability_id == :PHANTOM
    yield
  ensure
    @rating = nil
  end

  def self.rating?(pkmn)
    !@rating.nil? && @rating.equal?(pkmn)
  end
end

begin
  ChrookedLog.line("[chrooked:phantom] load prior_handler=#{!Battle::AbilityEffects::OnSwitchIn[:PHANTOM].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:PHANTOM,
    proc { |ability, battler, battle, switch_in|
      added = battler.canChangeType? && GameData::Type.exists?(:GHOST) && !battler.pbHasType?(:GHOST)
      if added
        battle.pbShowAbilitySplash(battler)
        battler.effects[PBEffects::ExtraType] = :GHOST
        battle.pbDisplay(_INTL("Ghost type was added to {1}!", battler.pbThis(true)))
        battle.pbHideAbilitySplash(battler)
      end
      ChrookedLog.line("[chrooked:phantom] OBS ability=true entry=true added=#{added}")
    }
  )
  Pokemon.class_eval do
    unless method_defined?(:chrooked_phantom_types)
      alias_method :chrooked_phantom_types, :types
      def types
        ret = chrooked_phantom_types
        return ret if !ChrookedPhantom.rating?(self) || ret.include?(:GHOST)
        ret + [:GHOST]
      end
    end
  end
  Battle::AI.class_eval do
    unless method_defined?(:chrooked_phantom_rate_replacement_pokemon)
      alias_method :chrooked_phantom_rate_replacement_pokemon, :rate_replacement_pokemon
      def rate_replacement_pokemon(idxBattler, pkmn, score)
        ChrookedPhantom.rating(pkmn) { chrooked_phantom_rate_replacement_pokemon(idxBattler, pkmn, score) }
      end
    end
  end
  # The holder, typed `types`, enters (Phantom or none).
  chrooked_phantom_entry = lambda do |t, spec, types, ability = spec[:ability]|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = ability
    holder.types = types
    holder.effects[PBEffects::ExtraType] = nil
    Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true) if ability
    [b, holder, foe]
  end
  chrooked_phantom_effect = lambda do |b, foe, holder, move_id|
    move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(move_id))
    move.calcType = move.pbCalcType(foe)
    Effectiveness.ineffective?(move.pbCalcTypeMod(move.calcType, foe, holder))
  end
  ($chrooked_selftest_cases ||= {})["phantom"] = {
    ability: :PHANTOM, control: nil, user: :ROTOM, foe: :SNORLAX, neutral: false,
    calc: [],
    checks: [
      ["electric_fire", ->(t, spec) {
        b, holder, foe = chrooked_phantom_entry.call(t, spec, [:ELECTRIC, :FIRE])
        "types=#{holder.pbTypes(true).join('/')} tackle_fails=#{chrooked_phantom_effect.call(b, foe, holder, :TACKLE)} " \
        "karate_chop_fails=#{chrooked_phantom_effect.call(b, foe, holder, :KARATECHOP)}"
      }],
      ["shadow_ball_stab", ->(t, spec) {
        b, holder, foe = chrooked_phantom_entry.call(t, spec, [:ELECTRIC, :FIRE])
        foe.pbChangeTypes(:QMARKS)
        with = t.hit(b, holder, foe, :SHADOWBALL)
        holder.effects[PBEffects::ExtraType] = nil
        without = t.hit(b, holder, foe, :SHADOWBALL)
        "with=#{with} without=#{without} stab=#{with > without}"
      }],
      ["reentry", ->(t, spec) {
        b, holder, _foe = chrooked_phantom_entry.call(t, spec, [:ELECTRIC, :FIRE])
        holder.pbInitEffects(false)
        out = holder.pbHasType?(:GHOST)
        Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
        "ghost_while_out=#{out} ghost_again=#{holder.pbHasType?(:GHOST)}"
      }],
      ["already_ghost", ->(t, spec) {
        _b, holder, _foe = chrooked_phantom_entry.call(t, spec, [:ELECTRIC, :GHOST])
        "extra_type=#{holder.effects[PBEffects::ExtraType] || 'none'}"
      }],
      ["forests_curse", ->(t, spec) {
        b, holder, foe = chrooked_phantom_entry.call(t, spec, [:ELECTRIC, :FIRE])
        curse = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:FORESTSCURSE))
        curse.pbEffectAgainstTarget(foe, holder)
        "types=#{holder.pbTypes(true).join('/')}"
      }],
      ["trick_or_treat", ->(t, spec) {
        b, holder, foe = chrooked_phantom_entry.call(t, spec, [:ELECTRIC, :FIRE])
        trick = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:TRICKORTREAT))
        "fails=#{trick.pbFailsAgainstTarget?(foe, holder, false)}"
      }],
      # The AI rates the holder's own Pokemon as a switch-in after the foe used Tackle:
      # with Phantom the Normal move is weighed against a Ghost, so it costs nothing.
      ["ai_switch", ->(t, spec) {
        b, holder, foe = chrooked_phantom_entry.call(t, spec, [:ELECTRIC, :FIRE], nil)
        foe.lastMoveUsed = :TACKLE
        ai = b.instance_variable_get(:@battleAI)   # Nova keeps it unexposed
        ai.create_ai_objects
        ai.set_up(holder.index)
        pkmn = holder.pokemon
        pkmn.form = 1   # Rotom-Heat, Electric/Fire: the party's own types have no Ghost
        pkmn.ability = spec[:ability]
        phantom = ai.rate_replacement_pokemon(holder.index, pkmn, 100)
        pkmn.ability = nil
        plain = ai.rate_replacement_pokemon(holder.index, pkmn, 100)
        "party_types=#{pkmn.types.join('/')} score_phantom=#{phantom} score_plain=#{plain} " \
        "ghost_weighed=#{phantom > plain}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:phantom] installed on OnSwitchIn and Battle::AI#rate_replacement_pokemon")
rescue StandardError => e
  ChrookedLog.error("[chrooked:phantom] ERROR #{e.class}: #{e.message}")
end
