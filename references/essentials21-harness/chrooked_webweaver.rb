# chrooked:webweaver
# ---------------------------------------------------------------------------
# Ruleset ability "webweaver": its own entry Sticky Web, plus Arena Trap (the Ruleset
# composes it as webweaver + arenatrap).
#
# HAND-WRITTEN WHOLE (mjolnir NV-28), as Thorned Succulent is (NV-26): an ability that
# lists itself cannot be a generated composition, so this file is the whole ability.
#   - its own part: OnSwitchIn lays Sticky Web on the foes' side unless one is there,
#     with the move's own message (it does not stack, as the move fails then);
#   - Arena Trap: Nova's TrappingByTarget handler, copied (a grounded foe cannot switch
#     or flee; Ghost types and Shed Shell are let go before Nova asks);
#   - by name: it answers hasActiveAbility?(:ARENATRAP), as a composed battler answers
#     for its parts, so the AI sees it.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md.
#     [chrooked:webweaver] OBS ability=true entry=true laid=<bool>   each entry
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
  ChrookedLog.line("[chrooked:webweaver] load prior_handler=#{!Battle::AbilityEffects::OnSwitchIn[:WEBWEAVER].nil?}")
  Battle::AbilityEffects::OnSwitchIn.add(:WEBWEAVER,
    proc { |ability, battler, battle, switch_in|
      laid = !battler.pbOpposingSide.effects[PBEffects::StickyWeb]
      if laid
        battle.pbShowAbilitySplash(battler)
        battler.pbOpposingSide.effects[PBEffects::StickyWeb] = true
        battle.pbDisplay(_INTL("A sticky web has been laid out beneath {1} feet!", battler.pbOfOpposingTeam(true)))
        battle.pbHideAbilitySplash(battler)
      end
      ChrookedLog.line("[chrooked:webweaver] OBS ability=true entry=true laid=#{laid}")
    }
  )
  Battle::AbilityEffects::TrappingByTarget.copy(:ARENATRAP, :WEBWEAVER)
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_webweaver_hasActiveAbility?)
      alias_method :chrooked_webweaver_hasActiveAbility?, :hasActiveAbility?
      def hasActiveAbility?(check_ability, ignore_fainted = false)
        asked = check_ability.is_a?(Array) ? check_ability : [check_ability]
        if asked.include?(:ARENATRAP) && chrooked_webweaver_hasActiveAbility?(:WEBWEAVER, ignore_fainted)
          return true
        end
        chrooked_webweaver_hasActiveAbility?(check_ability, ignore_fainted)
      end
    end
  end
  # The holder enters (Sticky Web preset on the foes' side), then the foe asks to switch.
  chrooked_webweaver_scene = lambda do |t, spec, web: false, foe_types: nil, foe_item: nil|
    b, holder, foe = t.pair(spec, :TACKLE)
    holder.ability = spec[:ability]
    foe.item = foe_item
    if foe_types
      foe.types = foe_types
      foe.effects[PBEffects::ExtraType] = nil
    end
    holder.pbOpposingSide.effects[PBEffects::StickyWeb] = web
    shown = []   # this throwaway battle's messages, to count the web's
    b.define_singleton_method(:pbDisplay) { |msg, &_blk| shown << msg }
    Battle::AbilityEffects.triggerOnSwitchIn(holder.ability, holder, b, true)
    "web=#{holder.pbOpposingSide.effects[PBEffects::StickyWeb]} web_messages=#{shown.count { |m| m.include?('sticky web') }} " \
    "foe_grounded=#{!foe.airborne?} can_switch=#{b.pbCanSwitchOut?(foe.index)}"
  end
  ($chrooked_selftest_cases ||= {})["webweaver"] = {
    ability: :WEBWEAVER, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["lays_web", ->(t, spec) { chrooked_webweaver_scene.call(t, spec) }],
      ["already_webbed", ->(t, spec) { chrooked_webweaver_scene.call(t, spec, web: true) }],
      ["grounded_trapped", ->(t, spec) { chrooked_webweaver_scene.call(t, spec) }],
      ["flying_free", ->(t, spec) { chrooked_webweaver_scene.call(t, spec, foe_types: [:FLYING]) }],
      ["shed_shell", ->(t, spec) { chrooked_webweaver_scene.call(t, spec, foe_item: :SHEDSHELL) }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:webweaver] installed: OnSwitchIn, Arena Trap copied")
rescue StandardError => e
  ChrookedLog.error("[chrooked:webweaver] ERROR #{e.class}: #{e.message}")
end
