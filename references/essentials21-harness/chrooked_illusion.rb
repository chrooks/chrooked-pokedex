# chrooked:illusion
# ---------------------------------------------------------------------------
# Ruleset behavior "illusion": the game's own Illusion (on entry it looks like the last
# conscious party member; a damaging hit breaks the disguise), and its moves hit 1.2x
# while the disguise holds.
#
# HAND-WRITTEN (mjolnir NV-25). Seam Battle::AbilityEffects::DamageCalcFromUser: a 1.2x
# power multiplier while effects[PBEffects::Illusion] holds the disguise. Setting it
# (pbInitEffects) and breaking it (OnBeingHit :ILLUSION) stay Nova's, so the boost ends
# exactly when Nova's own illusion does.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:illusion] OBS move=<ID> ability=true disguised=<bool>   each damage calc (EST from the AI)
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
  ChrookedLog.line("[chrooked:illusion] load prior_handler=" \
                   "#{!Battle::AbilityEffects::DamageCalcFromUser[:ILLUSION].nil?}")
  Battle::AbilityEffects::DamageCalcFromUser.add(:ILLUSION,
    proc { |ability, user, target, move, mults, power, type|
      disguised = !user.effects[PBEffects::Illusion].nil?
      mults[:power_multiplier] *= 1.2 if disguised
      if ChrookedLog::ENABLED
        tag = caller_locations(1, 6).any? { |l| l.path.to_s.include?("AIMove") } ? "EST" : "OBS"
        ChrookedLog.line("[chrooked:illusion] #{tag} move=#{move.id} ability=true disguised=#{disguised}")
      end
    }
  )
  # The holder leads a party of two, a Pikachu last, so Nova's pbInitEffects disguises it.
  chrooked_illusion_scene = lambda do |t, spec|
    holder = t.mon(spec[:user], [:TACKLE])
    holder.ability = spec[:ability]
    decoy = t.mon(:PIKACHU, [:TACKLE])
    foe = t.mon(spec[:foe], [:TACKLE])
    tt = GameData::TrainerType.keys.first
    t1 = NPCTrainer.new("LabA", tt)
    t1.party = [holder, decoy]
    t2 = NPCTrainer.new("LabB", tt)
    t2.party = [foe]
    b = Battle.new(Battle::DebugSceneNoVisuals.new, [holder, decoy], [foe], t1, t2)
    b.debug          = true
    b.controlPlayer  = true
    b.internalBattle = false
    b.pbCreateBattler(0, holder, 0)
    b.pbCreateBattler(1, foe, 0)
    b.battlers[0].pbChangeTypes(:QMARKS)
    b.battlers[1].pbChangeTypes(:QMARKS)
    [b, b.battlers[0], b.battlers[1]]
  end
  ($chrooked_selftest_cases ||= {})["illusion"] = {
    ability: :ILLUSION, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["entry", ->(t, spec) {
        _b, holder, _foe = chrooked_illusion_scene.call(t, spec)
        "disguised=#{!holder.effects[PBEffects::Illusion].nil?} species=#{holder.species} " \
        "shown=#{holder.displaySpecies}"
      }],
      ["disguised_hit", ->(t, spec) {
        b, holder, foe = chrooked_illusion_scene.call(t, spec)
        with = t.hit(b, holder, foe, :TACKLE)
        disguise = holder.effects[PBEffects::Illusion]
        holder.effects[PBEffects::Illusion] = nil
        bare = t.hit(b, holder, foe, :TACKLE)
        holder.effects[PBEffects::Illusion] = disguise
        "disguised=#{!disguise.nil?} with=#{with} bare=#{bare} boosted=#{with > bare}"
      }],
      ["broken", ->(t, spec) {
        b, holder, foe = chrooked_illusion_scene.call(t, spec)
        before = t.hit(b, holder, foe, :TACKLE)
        hit_by = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:TACKLE))
        Battle::AbilityEffects.triggerOnBeingHit(holder.ability, foe, holder, hit_by, b)   # Nova's own break
        after = t.hit(b, holder, foe, :TACKLE)
        holder.ability = nil
        none = t.hit(b, holder, foe, :TACKLE)
        "disguised=#{!holder.effects[PBEffects::Illusion].nil?} shown=#{holder.displaySpecies} " \
        "before=#{before} after=#{after} none=#{none} boosted=#{after > none}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:illusion] installed on DamageCalcFromUser")
rescue StandardError => e
  ChrookedLog.error("[chrooked:illusion] ERROR #{e.class}: #{e.message}")
end
