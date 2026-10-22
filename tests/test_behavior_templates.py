"""Behavior templates generate a port, its self-test case and its harness checks (NV-8).

A fake resolver stands in for the target's PBS: it knows a fixed set of moves, types
and abilities and returns None for anything else, like the Essentials ResolutionMap.
Each shape is rendered as the hand-written port it replaces (Kindle, Overcharge,
Chitinize, Striker / Martial Artist), and `ruby -c` checks the Ruby parses (skipped
where ruby is absent).
"""

import shutil
import subprocess
from dataclasses import replace

import pytest

from chrooked_pokedex.behavior.templates import (
    TemplateError,
    harness_checks,
    render_essentials21,
    validate,
    validate_spec,
)
from chrooked_pokedex.model.behavior_spec import (
    BehaviorEffect,
    BehaviorSpec,
    BehaviorTemplate,
    BehaviorTestCase,
)

pytestmark = pytest.mark.unit


class _Names:
    MOVES = {
        "Flamethrower": "FLAMETHROWER", "Surf": "SURF", "Ember": "EMBER",
        "Thunderbolt": "THUNDERBOLT", "Ice Beam": "ICEBEAM", "Tackle": "TACKLE",
        "X-Scissor": "XSCISSOR", "High Jump Kick": "HIGHJUMPKICK", "Mach Punch": "MACHPUNCH",
        "Body Slam": "BODYSLAM", "Hyper Voice": "HYPERVOICE",
    }
    TYPES = {"fire": "FIRE", "electric": "ELECTRIC", "bug": "BUG"}
    ITEMS = {"utility umbrella": "UTILITYUMBRELLA"}

    def move(self, name):
        return self.MOVES.get(name)

    def type(self, name):
        return self.TYPES.get(name.lower())

    def ability(self, name):
        return name.upper().replace(" ", "")

    def item(self, name):
        return self.ITEMS.get(name.lower())


def _spec(cid, shape, params, probes, name=None):
    return BehaviorSpec(
        name=name or cid.title(), chrooked_id=cid, applies_to="ability",
        effects=(BehaviorEffect(summary=f"The {cid} effect.", trigger="damage-calc", effect="x"),),
        test_cases=tuple(BehaviorTestCase(given=f"case {i}", expect="x") for i in range(1, len(probes) + 1)),
        template=BehaviorTemplate(shape=shape, params=params, probes=tuple(probes)),
    )


KINDLE = _spec("kindle", "type_boost", {"type": "Fire", "multiplier": 1.5, "control": "BLAZE"}, [
    {"move": "Flamethrower", "result": "boosted"},
    {"move": "Surf", "result": "normal"},
    {"move": "Ember", "result": "boosted"},
])
OVERCHARGE = _spec("overcharge", "type_boost",
                   {"type": "Electric", "multiplier": 1.5, "pinch": True, "control": "BLAZE"}, [
    {"move": "Thunderbolt", "result": "boosted", "hp": 0.25},
    {"move": "Thunderbolt", "result": "normal"},
    {"move": "Ice Beam", "result": "normal", "hp": 0.25},
])
CHITINIZE = _spec("chitinize", "type_conversion", {"type": "Bug", "control": "AERILATE"}, [
    {"move": "Tackle", "converted": True},
    {"move": "Tackle", "converted": True},
    {"move": "X-Scissor", "converted": False},
])
STRIKER = _spec("striker", "flag_boost", {"flags": ["kicking"], "multiplier": 1.3}, [
    {"move": "High Jump Kick", "result": "boosted"},
    {"move": "Tackle", "result": "normal"},
    {"move": "High Jump Kick", "result": "normal", "holder": False},
])
MARTIALARTIST = _spec("martialartist", "flag_boost",
                      {"flags": ["punching", "kicking"], "multiplier": 1.3, "control": "IRONFIST"}, [
    {"move": "Mach Punch", "result": "boosted"},
    {"move": "High Jump Kick", "result": "boosted"},
    {"move": "Tackle", "result": "normal"},
], name="Martial Artist")
FORESTRY = _spec("forestry", "conditional_boost", {"terrain": "grassy", "multiplier": 1.3}, [
    {"move": "Body Slam", "result": "boosted"},
    {"move": "Body Slam", "result": "normal", "field": False},
    {"move": "Body Slam", "result": "normal", "airborne": True},
])
DOWNPOUR = _spec("downpour", "conditional_boost", {"weather": "rain", "moves": "higher_stat", "multiplier": 1.5}, [
    {"move": "Body Slam", "result": "boosted", "stats": "physical"},
    {"move": "Hyper Voice", "result": "boosted", "stats": "special"},
    {"move": "Hyper Voice", "result": "normal", "stats": "physical"},
    {"move": "Body Slam", "result": "normal", "stats": "physical", "item": "Utility Umbrella"},
])
ALL = [KINDLE, OVERCHARGE, CHITINIZE, STRIKER, MARTIALARTIST, FORESTRY, DOWNPOUR]


def _render(spec):
    return render_essentials21(spec, _Names())


def _verdicts(spec):
    return [(c["select"], c["expect"]) for c in harness_checks(spec, _Names())]


# --- the port --------------------------------------------------------------------


@pytest.mark.parametrize("spec", ALL, ids=lambda s: s.chrooked_id)
def test_every_port_is_a_tagged_marker_gated_v21_registry_entry(spec):
    text = _render(spec)
    assert text.startswith(f"# chrooked:{spec.chrooked_id}\n")  # the installer's validity tag
    assert f"ruleset/behaviors/{spec.chrooked_id}.yaml" in text
    assert "Battle::AbilityEffects::DamageCalcFromUser" in text
    assert 'ENABLED = File.exist?(File.expand_path("chrooked-oracle.on"))' in text
    assert f'($chrooked_selftest_cases ||= {{}})["{spec.chrooked_id}"] = {{' in text
    assert "user: :NUMEL, foe: :SNORLAX, neutral: true" in text
    assert "PokeBattle_" not in text and "{{" not in text
    assert text.endswith("end\n")


def test_type_boost_is_blazes_shape_without_the_hp_check():
    text = _render(KINDLE)
    assert "chrooked_table.add(:KINDLE," in text
    assert "      boosted = (type == :FIRE)\n" in text
    assert "mults[:attack_multiplier] *= 1.5 if boosted" in text
    assert "hp_low" not in text
    assert "control: :BLAZE" in text
    assert "calc: [[:FLAMETHROWER, 1.0], [:SURF, 1.0], [:EMBER, 1.0]]" in text
    assert "without: []" in text
    assert "fight: [:FLAMETHROWER, :SURF, :EMBER]" in text


def test_pinch_type_boost_gates_on_a_third_of_max_hp():
    text = _render(OVERCHARGE)
    assert "      hp_low  = user.hp <= user.totalhp / 3\n      boosted = hp_low && type == :ELECTRIC\n" in text
    assert '"hp_low=#{hp_low} result=' in text
    assert "calc: [[:THUNDERBOLT, 0.25], [:THUNDERBOLT, 1.0], [:ICEBEAM, 0.25]]" in text
    assert "fight: [:THUNDERBOLT, :ICEBEAM]" in text


def test_type_conversion_is_aerilates_pair():
    text = _render(CHITINIZE)
    assert "Battle::AbilityEffects::ModifyMoveBaseType.add(:CHITINIZE," in text
    assert "next if type != :NORMAL || !GameData::Type.exists?(:BUG)" in text
    assert "next :BUG" in text
    assert "mults[:power_multiplier] *= 1.2 if move.powerBoost" in text  # the default multiplier
    assert "calc: [[:TACKLE, 1.0], [:XSCISSOR, 1.0]]" in text  # the repeated Tackle probe is measured once
    assert "control: :AERILATE" in text


def test_flag_boost_is_iron_fists_shape_on_the_flags():
    striker, martial = _render(STRIKER), _render(MARTIALARTIST)
    assert "category = move.flags.find { |f| f[/^(Kicking)$/i] }" in striker
    assert "mults[:power_multiplier] *= 1.3 if category" in striker
    assert "control: nil" in striker
    assert "calc: [[:HIGHJUMPKICK, 1.0], [:TACKLE, 1.0]]" in striker
    assert "without: [:HIGHJUMPKICK]" in striker
    assert "chrooked_table.add(:MARTIALARTIST," in martial
    assert "f[/^(Punching|Kicking)$/i]" in martial


def test_terrain_boost_is_the_hand_proven_forestry():
    text = _render(FORESTRY)
    # The code lines of the NV-9 hand port, which scored 3/3 in the lab.
    assert ("      terrain  = user.battle.field.terrain\n"
            "      grounded = user.affectedByTerrain?\n"
            "      boosted  = terrain == :Grassy && grounded\n"
            "      mults[:power_multiplier] *= 1.3 if boosted\n") in text
    assert 'move=#{move.id} ability=true terrain=#{terrain} " \\\n' in text
    assert '"grounded=#{grounded} result=#{boosted ? \'BOOSTED\' : \'NORMAL\'}")' in text
    assert ("calc: [[:BODYSLAM, 1.0, {terrain: :Grassy}], [:BODYSLAM, 1.0, {}], "
            "[:BODYSLAM, 1.0, {terrain: :Grassy, airborne: true}]]") in text
    assert "fight: [:BODYSLAM]" in text


def test_weather_boost_on_the_higher_stat_is_solar_powers_shape():
    text = _render(DOWNPOUR)
    assert ("      weather = user.battle.pbWeather\n"
            "      higher  = (user.attack >= user.spatk) ? :physical : :special\n"
            "      boosted = [:Rain, :HeavyRain].include?(user.effectiveWeather) &&\n"
            "                (higher == :physical ? move.physicalMove? : move.specialMove?)\n"
            "      mults[:attack_multiplier] *= 1.5 if boosted\n") in text
    assert "ability=true weather=#{weather} item=#{user.item_id || 'none'} \" \\\n" in text
    assert '"higher=#{higher} result=' in text
    assert ("calc: [[:BODYSLAM, 1.0, {weather: :Rain, stats: :physical}], "
            "[:HYPERVOICE, 1.0, {weather: :Rain, stats: :special}], "
            "[:HYPERVOICE, 1.0, {weather: :Rain, stats: :physical}], "
            "[:BODYSLAM, 1.0, {weather: :Rain, item: :UTILITYUMBRELLA, stats: :physical}]]") in text
    assert "Utility Umbrella clears it" in text  # the header says why the item matters


def test_hail_counts_novas_snowstorm_too():
    whiteout = replace(DOWNPOUR, chrooked_id="whiteout", name="Whiteout", template=replace(
        DOWNPOUR.template, params={"weather": "hail", "moves": "higher_stat", "multiplier": 1.5},
        probes=DOWNPOUR.template.probes[:3]), test_cases=DOWNPOUR.test_cases[:3])
    text = _render(whiteout)
    assert "[:Hail, :Snowstorm].include?(user.effectiveWeather)" in text
    assert "weather: :Hail, stats: :physical" in text


def test_fight_keeps_at_most_four_moves():
    moves = ["Flamethrower", "Surf", "Ember", "Tackle", "Thunderbolt"]
    spec = _spec("kindle", "type_boost", {"type": "Fire", "multiplier": 1.5},
                 [{"move": m, "result": "normal"} for m in moves])
    assert "fight: [:FLAMETHROWER, :SURF, :EMBER, :TACKLE]\n" in _render(spec)


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby not installed")
@pytest.mark.parametrize("spec", ALL, ids=lambda s: s.chrooked_id)
def test_rendered_port_is_valid_ruby(spec, tmp_path):
    port = tmp_path / f"chrooked_{spec.chrooked_id}.rb"
    port.write_text(_render(spec), encoding="utf-8")
    result = subprocess.run(["ruby", "-c", str(port)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Syntax OK" in result.stdout


# --- the harness checks ----------------------------------------------------------


def test_type_boost_checks():
    assert _verdicts(KINDLE) == [
        ({"move": "FLAMETHROWER", "ability": "true"}, {"result": "BOOSTED"}),
        ({"move": "SURF", "ability": "true"}, {"result": "NORMAL"}),
        ({"move": "EMBER", "ability": "true"}, {"result": "BOOSTED"}),
    ]


def test_pinch_checks_select_the_hp_side():
    assert _verdicts(OVERCHARGE) == [
        ({"move": "THUNDERBOLT", "ability": "true", "hp_low": "true"}, {"result": "BOOSTED"}),
        ({"move": "THUNDERBOLT", "ability": "true", "hp_low": "false"}, {"result": "NORMAL"}),
        ({"move": "ICEBEAM", "ability": "true", "hp_low": "true"}, {"result": "NORMAL"}),
    ]


def test_type_conversion_checks():
    assert _verdicts(CHITINIZE) == [
        ({"move": "TACKLE", "ability": "true"}, {"converted": "BUG", "boosted": "true"}),
        ({"move": "TACKLE", "ability": "true"}, {"converted": "BUG", "boosted": "true"}),
        ({"move": "XSCISSOR", "ability": "true"}, {"converted": "none", "boosted": "false"}),
    ]


def test_terrain_boost_checks_select_the_scene():
    assert _verdicts(FORESTRY) == [
        ({"move": "BODYSLAM", "ability": "true", "terrain": "Grassy", "grounded": "true"}, {"result": "BOOSTED"}),
        ({"move": "BODYSLAM", "ability": "true", "terrain": "None", "grounded": "true"}, {"result": "NORMAL"}),
        ({"move": "BODYSLAM", "ability": "true", "terrain": "Grassy", "grounded": "false"}, {"result": "NORMAL"}),
    ]


def test_weather_boost_checks_select_weather_item_and_higher_stat():
    assert _verdicts(DOWNPOUR) == [
        ({"move": "BODYSLAM", "ability": "true", "weather": "Rain", "item": "none", "higher": "physical"},
         {"result": "BOOSTED"}),
        ({"move": "HYPERVOICE", "ability": "true", "weather": "Rain", "item": "none", "higher": "special"},
         {"result": "BOOSTED"}),
        ({"move": "HYPERVOICE", "ability": "true", "weather": "Rain", "item": "none", "higher": "physical"},
         {"result": "NORMAL"}),
        # The raw field weather is still Rain; the umbrella clears it for the holder only.
        ({"move": "BODYSLAM", "ability": "true", "weather": "Rain", "item": "UTILITYUMBRELLA", "higher": "physical"},
         {"result": "NORMAL"}),
    ]


def test_conditional_stage_text_sets_the_scene():
    forestry = [c["stage"] for c in harness_checks(FORESTRY, _Names())]
    assert forestry == [
        "With your Forestry user on Grassy Terrain, use Body Slam on the foe.",
        "With your Forestry user with no terrain, use Body Slam on the foe.",
        "With your Forestry user (airborne) on Grassy Terrain, use Body Slam on the foe.",
    ]
    assert harness_checks(DOWNPOUR, _Names())[3]["stage"] == \
        "With your Downpour user (higher stat Attack, holding Utility Umbrella) in rain, use Body Slam on the foe."


def test_without_the_ability_checks_the_selftests_own_line():
    assert _verdicts(STRIKER)[2] == ({"move": "HIGHJUMPKICK", "ability": "false"}, {"result": "NORMAL"})


def test_stage_text_names_the_action():
    stages = [c["stage"] for c in harness_checks(OVERCHARGE, _Names())]
    assert stages[0] == "With your Overcharge user at 1/4 max HP, use Thunderbolt on the foe."
    assert stages[1] == "With your Overcharge user at full HP, use Thunderbolt on the foe."
    assert harness_checks(STRIKER, _Names())[2]["stage"] == "With a Pokemon WITHOUT Striker, use High Jump Kick on the foe."


@pytest.mark.parametrize("spec", ALL, ids=lambda s: s.chrooked_id)
def test_every_key_a_check_reads_is_logged_by_the_port(spec):
    text = _render(spec)
    for select, expect in _verdicts(spec):
        for key in {**select, **expect}:
            assert f"{key}=" in text, f"{spec.chrooked_id} never logs '{key}='"


# --- names the target lacks ------------------------------------------------------


def test_unresolved_names_fail_naming_each():
    spec = replace(KINDLE, template=replace(KINDLE.template, probes=(
        {"move": "Flamethrower", "result": "boosted"},
        {"move": "Sludge Wave", "result": "normal"},
        {"move": "Hyper Beam", "result": "normal"},
    )))
    with pytest.raises(TemplateError, match="the target has no move 'Sludge Wave', move 'Hyper Beam'"):
        _render(spec)
    with pytest.raises(TemplateError, match="Sludge Wave"):
        harness_checks(spec, _Names())


def test_unknown_type_fails():
    spec = replace(KINDLE, template=replace(KINDLE.template, params={"type": "Cosmic", "multiplier": 1.5}))
    with pytest.raises(TemplateError, match="type 'Cosmic'"):
        _render(spec)


def test_unknown_item_fails():
    spec = replace(DOWNPOUR, template=replace(DOWNPOUR.template, probes=DOWNPOUR.template.probes[:3] + (
        {"move": "Body Slam", "result": "normal", "stats": "physical", "item": "Rain Hat"},)))
    with pytest.raises(TemplateError, match="item 'Rain Hat'"):
        _render(spec)


def test_a_move_spec_cannot_use_an_ability_template():
    with pytest.raises(TemplateError, match="applies to a move"):
        _render(replace(KINDLE, applies_to="move"))


# --- the effects guard (NV-9) ----------------------------------------------------


def test_a_spec_with_more_effects_than_a_template_generates_is_refused():
    """Infernal Maw boosts biting moves AND adds a burn chance: a flag_boost template
    would mark it installed with the burn missing, so it is refused."""
    two = replace(STRIKER, effects=STRIKER.effects + (
        BehaviorEffect(summary="Kicking moves may burn.", trigger="damage-calc", effect="20% burn"),))
    with pytest.raises(TemplateError, match="exactly one effect, and this spec has 2"):
        validate_spec(two)
    with pytest.raises(TemplateError, match="exactly one effect"):
        _render(two)


def test_the_proven_specs_pass_the_spec_check():
    for spec in ALL:
        validate_spec(spec)


# --- validate --------------------------------------------------------------------


def _template(shape="type_boost", params=None, probes=None):
    params = {"type": "Fire", "multiplier": 1.5} if params is None else params
    probes = [{"move": "Ember", "result": "boosted"}] if probes is None else probes
    return BehaviorTemplate(shape=shape, params=params, probes=tuple(probes))


def test_the_proven_specs_validate():
    for spec in ALL:
        validate(spec.template, len(spec.test_cases))


@pytest.mark.parametrize(("template", "message"), [
    (_template(shape="beam_boost"), "unknown shape 'beam_boost'"),
    (_template(params={"type": "Fire"}), "needs params multiplier"),
    (_template(params={"type": "Fire", "multiplier": 1.5, "colour": "red"}), "unknown params colour"),
    (_template(params={"type": "Fire", "multiplier": "1.5"}), "multiplier must be a positive number"),
    (_template(params={"type": "Fire", "multiplier": True}), "multiplier must be a positive number"),
    (_template(params={"type": "", "multiplier": 1.5}), "params.type"),
    (_template(params={"type": "Fire", "multiplier": 1.5, "pinch": "yes"}), "pinch must be true or false"),
    (_template(params={"type": "Fire", "multiplier": 1.5, "control": "Blaze"}), "INTERNAL ability name"),
    (_template("flag_boost", {"flags": ["kick"], "multiplier": 1.3}), "unknown move flags kick"),
    (_template("flag_boost", {"flags": [], "multiplier": 1.3}), "non-empty list"),
    (_template(probes=[{"result": "boosted"}]), "needs a move name"),
    (_template(probes=[{"move": "Ember", "result": "BOOSTED"}]), "result must be boosted or normal"),
    (_template(probes=[{"move": "Ember", "result": "boosted", "speed": 1}]), "unknown fields speed"),
    (_template(probes=[{"move": "Ember", "result": "boosted", "hp": 0}]), "hp must be a fraction"),
    (_template(probes=[{"move": "Ember", "result": "boosted", "hp": 1.5}]), "hp must be a fraction"),
    (_template(probes=[{"move": "Ember", "result": "boosted", "holder": False}]), "cannot be boosted"),
    (_template(probes=[{"move": "Ember", "result": "normal", "holder": False, "hp": 0.5}]), "drop it"),
    (_template("type_conversion", {"type": "Bug"}, [{"move": "Tackle", "converted": "yes"}]),
     "converted must be true or false"),
    (_template("type_conversion", {"type": "Bug"}, [{"move": "Tackle", "converted": False, "holder": False}]),
     "unknown fields holder"),
    (_template("conditional_boost", {"multiplier": 1.3}), "exactly one of params.weather or params.terrain"),
    (_template("conditional_boost", {"weather": "rain", "terrain": "grassy", "multiplier": 1.3}),
     "exactly one of params.weather or params.terrain"),
    (_template("conditional_boost", {"weather": "fog", "multiplier": 1.3}), "params.weather must be one of"),
    (_template("conditional_boost", {"terrain": "swamp", "multiplier": 1.3}), "params.terrain must be one of"),
    (_template("conditional_boost", {"weather": "rain", "moves": "special", "multiplier": 1.5}),
     "params.moves must be one of"),
    (_template("conditional_boost", {"weather": "rain", "moves": "higher_stat", "multiplier": 1.5}),
     "needs stats: physical or special"),
    (_template("conditional_boost", {"weather": "rain", "multiplier": 1.5},
               [{"move": "Ember", "result": "boosted", "stats": "physical"}]), "unknown fields stats"),
    (_template("conditional_boost", {"weather": "rain", "multiplier": 1.5},
               [{"move": "Ember", "result": "normal", "airborne": True}]), "unknown fields airborne"),
    (_template("conditional_boost", {"terrain": "grassy", "multiplier": 1.3},
               [{"move": "Ember", "result": "normal", "item": "Utility Umbrella"}]), "unknown fields item"),
    (_template("conditional_boost", {"terrain": "grassy", "multiplier": 1.3},
               [{"move": "Ember", "result": "normal", "holder": False}]), "unknown fields holder"),
    (_template("conditional_boost", {"terrain": "grassy", "multiplier": 1.3},
               [{"move": "Ember", "result": "normal", "field": "no"}]), "field must be true or false"),
])
def test_validate_refuses(template, message):
    with pytest.raises(TemplateError, match=message):
        validate(template, len(template.probes))


def test_validate_refuses_misaligned_probes():
    with pytest.raises(TemplateError, match="1 probes for 3 test_cases"):
        validate(_template(), 3)
