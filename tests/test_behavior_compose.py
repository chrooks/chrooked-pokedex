"""Composed abilities on Essentials 21 (mjolnir NV-15): one file per composed ability
wires its parts' handlers, and its proof is the parts' own probes plus a damage
comparison per vanilla part.

A fake resolver stands in for the target's PBS, as in test_behavior_templates.py.
"""

import shutil
import subprocess

import pytest

from chrooked_pokedex.behavior import compose
from chrooked_pokedex.behavior.compose import CompositionError, harness_checks, render_essentials21
from chrooked_pokedex.model.behavior_spec import (
    BehaviorEffect,
    BehaviorSpec,
    BehaviorTemplate,
    BehaviorTestCase,
)
from chrooked_pokedex.model.ruleset import Ruleset
from chrooked_pokedex.model.schema import AbilityDef

pytestmark = pytest.mark.unit


class _Names:
    MOVES = {"Crunch": "CRUNCH", "Hyper Voice": "HYPERVOICE", "Air Slash": "AIRSLASH", "Tackle": "TACKLE", "Shadow Ball": "SHADOWBALL",
             "Flamethrower": "FLAMETHROWER", "Ember": "EMBER", "Surf": "SURF"}
    TYPES = {"fire": "FIRE", "ghost": "GHOST"}
    MISSING_ABILITIES: frozenset = frozenset()

    def move(self, name):
        return self.MOVES.get(name)

    def type(self, name):
        return self.TYPES.get(name.lower())

    def ability(self, name):
        return None if name in self.MISSING_ABILITIES else name.upper().replace(" ", "")

    def item(self, name):
        return None


def _spec(cid, shape, params, probes):
    return BehaviorSpec(
        name=cid.title(), chrooked_id=cid, applies_to="ability",
        effects=(BehaviorEffect(summary=f"The {cid} effect.", trigger="x", effect="x"),),
        test_cases=tuple(BehaviorTestCase(given=f"{cid} case {i}", expect="x") for i in range(1, len(probes) + 1)),
        template=BehaviorTemplate(shape=shape, params=params, probes=tuple(probes)),
    )


CARNIVORE = _spec("carnivore", "ko_effect", {"heal": 0.25}, [
    {"kos": 1, "effect": True, "hp": 0.5},
    {"kos": 0, "effect": False, "hp": 0.5},
])
PYRE = _spec("pyre", "hit_status", {"status": "burn", "chance": 30, "type": "Ghost"}, [
    {"move": "Shadow Ball", "inflicts": True},
    {"move": "Flamethrower", "inflicts": False},
])
KINDLE = _spec("kindle", "type_boost", {"type": "Fire", "multiplier": 1.5, "control": "BLAZE"}, [
    {"move": "Ember", "result": "boosted"},
    {"move": "Surf", "result": "normal"},
])


def _ruleset(parts, *, specs=(CARNIVORE, PYRE, KINDLE), name="Apex Predator", cid="apexpredator"):
    abilities = {cid: AbilityDef(name=name, chrooked_id=cid, description="Biting boost. A KO heals.",
                                 behaviors=tuple(parts))}
    return Ruleset(abilities=abilities, behaviors={s.chrooked_id: s for s in specs})


def _render(ruleset, cid="apexpredator", names=None):
    return render_essentials21(ruleset.abilities[cid], ruleset, names or _Names())


def _checks(ruleset, cid="apexpredator"):
    return harness_checks(ruleset.abilities[cid], ruleset, _Names())


# --- the file ----------------------------------------------------------------------


def test_a_composed_ability_registers_its_parts_and_one_merged_selftest_case():
    text = _render(_ruleset(["carnivore", "strongjaw"]))
    assert text.startswith("# chrooked:apexpredator\n")  # the installer's validity tag
    assert "ruleset/abilities/apexpredator.yaml" in text
    assert 'ChrookedCompose.register(:APEXPREDATOR, "apexpredator", ' \
           '[[:CARNIVORE, "carnivore"], [:STRONGJAW, "strongjaw"]])' in text
    assert '($chrooked_selftest_cases ||= {})["apexpredator"] = {' in text
    assert "ability: :APEXPREDATOR, control: nil" in text
    assert "    ko: [{kos: 1, hp: 0.5}, {kos: 0, hp: 0.5}],\n    compare: [[:CRUNCH, :STRONGJAW]],\n" in text
    assert "fight: [:TACKLE, :CRUNCH]\n" in text
    assert "{{" not in text and text.endswith("end\n")


def test_the_wiring_waits_for_the_first_battle_and_retags_the_parts_lines():
    text = _render(_ruleset(["carnivore", "strongjaw"]))
    assert "unless defined?(ChrookedCompose)" in text
    assert "alias_method :chrooked_compose_initialize, :initialize" in text
    assert "ChrookedCompose.wire\n" in text
    assert "alias_method :chrooked_compose_line, :line" in text
    assert 'line = "[chrooked:#{tag}] #{msg.delete_prefix(prefix)} part=#{part}"' in text
    # Each rule names registries whose trigger reads the result that way (Nova's 008_Battle_AbilityEffects.rb).
    # Every other registry runs each part (#121), so no pair of parts goes uncombined.
    assert "THREAD = [:SpeedCalc, :WeightCalc, :PriorityChange, :ModifyMoveBaseType," in text
    assert "ANY    = [:MoveImmunity, :MoveBlocking, :StatLossImmunity," in text
    assert "SUM    = [:PriorityBracketChange]" in text
    assert "has no rule to combine them" not in text


def test_two_ported_parts_merge_their_phases_and_keep_the_first_control():
    text = _render(_ruleset(["pyre", "kindle"], name="Requiem", cid="requiem"), cid="requiem")
    assert "control: :BLAZE" in text
    assert "calc: [[:EMBER, 1.0], [:SURF, 1.0]],\n    chance: [\n" in text
    assert "fight: [:SHADOWBALL, :FLAMETHROWER, :EMBER, :SURF]\n" in text  # at most four


def test_vanilla_parts_each_get_a_comparison():
    text = _render(_ruleset(["sharpness", "toughclaws"], name="Razor Edge", cid="razoredge"), cid="razoredge")
    assert "compare: [[:AIRSLASH, :SHARPNESS], [:TACKLE, :TOUGHCLAWS]]," in text
    assert "calc: []," in text


def test_each_proof_kind_has_its_compare_entry_and_a_by_name_part_its_identity():
    """NV-16: a part checked by name is proven by what it changes and by its name."""
    rs = _ruleset(["levitate", "suctioncups", "clearbody", "guts", "moxie", "scrappy", "gorillatactics"],
                  name="Everything", cid="everything")
    text = _render(rs, cid="everything")
    assert ("compare: [[nil, :LEVITATE, :airborne], [nil, :SUCTIONCUPS, :forced_out], "
            "[nil, :CLEARBODY, :stat_drop], [:TACKLE, :GUTS, :hit, {status: :BURN}], [nil, :MOXIE, :ko], "
            "[:TACKLE, :SCRAPPY, :hit, {target_types: [:GHOST]}], [:TACKLE, :GORILLATACTICS], "
            "[:TACKLE, :GORILLATACTICS, :locked]],\n") in text
    assert "identity: [:LEVITATE, :SUCTIONCUPS, :GUTS, :SCRAPPY, :GORILLATACTICS],\n" in text
    checks, cases = _checks(rs, cid="everything")
    assert checks[0] == {
        "stage": "Measured by the self-test: Everything's holder is airborne.",
        "select": {"move": "NONE", "ability": "true", "source": "selftest", "part": "LEVITATE", "kind": "airborne"},
        "expect": {"changed": "true", "result": "MATCHES"}}
    assert checks[1]["select"] == {"case": "identity", "part": "LEVITATE", "source": "selftest"}
    assert checks[1]["expect"] == {"has": "true", "array": "true", "other": "false"}
    assert "Guts: Everything uses Tackle while it has a burn" in [c.given for c in cases]
    assert "Scrappy: Everything uses Tackle on a Ghost-type foe" in [c.given for c in cases]
    assert not any(c["select"].get("part") == "CLEARBODY" and c["select"].get("case") for c in checks)


def test_field_and_target_side_proofs():
    """NV-17: parts measured on a field, or as the foe's target."""
    rs = _ruleset(["slushrush", "soundproof", "bulletproof", "battlearmor", "grassysurge", "grasspelt"],
                  name="Fortress", cid="fortress")
    text = _render(rs, cid="fortress")
    assert ("compare: [[nil, :SLUSHRUSH, :speed, {weather: :Hail}], [:HYPERVOICE, :SOUNDPROOF, :immune], "
            "[:SHADOWBALL, :BULLETPROOF, :immune], [:TACKLE, :BATTLEARMOR, :crit_taken], "
            "[nil, :GRASSYSURGE, :switch_in], [:TACKLE, :GRASSPELT, :hit_taken, {terrain: :Grassy}]],\n") in text
    assert "identity: [:SOUNDPROOF],\n" in text  # Uproar asks for it by name
    _, cases = _checks(rs, cid="fortress")
    assert "Grass Pelt: a foe's Tackle hits Fortress's holder on Grassy Terrain" in [c.given for c in cases]
    assert "Slush Rush: Fortress's holder's Speed in hail" in [c.given for c in cases]


def test_the_holder_answers_to_its_parts_names():
    text = _render(_ruleset(["carnivore", "strongjaw"]))
    assert "alias_method :chrooked_compose_has_active_ability?, :hasActiveAbility?" in text
    assert "parts = ChrookedCompose.parts_of(@ability_id)" in text
    assert "return false if parts.nil? || !abilityActive?(ignore_fainted, check_ability)" in text
    assert "alias hasWorkingAbility hasActiveAbility?" in text


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby not installed")
def test_the_file_is_valid_ruby(tmp_path):
    port = tmp_path / "chrooked_apexpredator.rb"
    port.write_text(_render(_ruleset(["carnivore", "strongjaw"])), encoding="utf-8")
    result = subprocess.run(["ruby", "-c", str(port)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# Stubs for the classes _COMPOSE reopens, then each rule's result for two parts.
_COMBINE_PROBE = """
module ChrookedLog
  ENABLED = false
  def self.line(msg); end
  def self.error(msg); raise msg; end
end
class Battle; def initialize(*); end; end
class Battle::Battler; def hasActiveAbility?(*); false; end; end
%s
c = ChrookedCompose
add = [["a", proc { |_s, _b, v| v + 1 }], ["b", proc { |_s, _b, v| v * 10 }]]
yes = [["a", proc { nil }], ["b", proc { true }]]
pri = [["a", proc { -1 }], ["b", proc { 1 }]]
seen = []
each = [["a", proc { seen << :a; nil }], ["b", proc { seen << :b; nil }]]
puts c.combine(:SpeedCalc, nil, add).call(:X, nil, 2)
puts c.combine(:MoveImmunity, nil, yes).call(:X)
puts c.combine(:PriorityBracketChange, nil, pri).call(:X)
c.combine(:EndOfRoundEffect, nil, each).call(:X)
puts seen.join(",")
"""


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby not installed")
def test_every_registry_combines_two_parts(tmp_path):
    probe = tmp_path / "probe.rb"
    probe.write_text(_COMBINE_PROBE % compose._COMPOSE, encoding="utf-8")
    result = subprocess.run(["ruby", str(probe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    # Speed threads (2+1)*10; immunity is any; brackets add; others run both parts.
    assert result.stdout.split() == ["30", "true", "0", "a,b"]


# --- the checks --------------------------------------------------------------------


def test_a_ported_parts_checks_select_its_retagged_lines():
    checks, cases = _checks(_ruleset(["carnivore", "strongjaw"]))
    assert [(c["select"], c["expect"]) for c in checks] == [
        ({"ability": "true", "kos": "1", "hp_full": "false", "part": "carnivore"}, {"result": "HEALED"}),
        ({"ability": "true", "kos": "0", "hp_full": "false", "part": "carnivore"}, {"result": "NONE"}),
        ({"move": "CRUNCH", "ability": "true", "source": "selftest", "part": "STRONGJAW", "kind": "hit"},
         {"changed": "true", "result": "MATCHES"}),
    ]
    assert [c.given for c in cases] == ["Carnivore: carnivore case 1", "Carnivore: carnivore case 2",
                                        "Strong Jaw: Apex Predator uses Crunch"]


def test_a_check_on_the_selftests_own_line_has_no_part():
    """The self-test logs a rate under the mechanic it runs, with no part to name."""
    checks, _ = _checks(_ruleset(["pyre", "kindle"], name="Requiem", cid="requiem"), cid="requiem")
    assert "part" not in checks[0]["select"] and checks[0]["select"]["source"] == "selftest"
    assert checks[2]["select"] == {"move": "EMBER", "ability": "true", "part": "kindle"}


# --- not composable yet, and refused ---------------------------------------------


@pytest.mark.parametrize("parts", [
    ["carnivore", "pickup"],        # a vanilla part with no proof in VANILLA_PARTS
    ["apexpredator", "strongjaw"],  # lists itself
])
def test_a_part_that_is_not_composable_yet_leaves_the_ability_data_only(parts):
    assert _render(_ruleset(parts)) is None
    with pytest.raises(CompositionError, match="not composable on this target yet"):
        _checks(_ruleset(parts))


def test_a_ruleset_part_without_a_template_is_not_composable_yet():
    unported = BehaviorSpec(name="Mawcannon", chrooked_id="mawcannon", applies_to="ability")
    assert _render(_ruleset(["mawcannon", "strongjaw"], specs=(unported,))) is None


def test_a_target_without_the_ability_is_skipped():
    class NoApex(_Names):
        MISSING_ABILITIES = frozenset({"Apex Predator"})

    assert _render(_ruleset(["carnivore", "strongjaw"]), names=NoApex()) is None


def test_a_target_without_a_vanilla_part_or_its_proof_move_is_refused():
    class NoJaw(_Names):
        MISSING_ABILITIES = frozenset({"Strong Jaw"})

    class NoCrunch(_Names):
        MOVES = {k: v for k, v in _Names.MOVES.items() if k != "Crunch"}

    with pytest.raises(CompositionError, match="no ability 'Strong Jaw'"):
        _render(_ruleset(["carnivore", "strongjaw"]), names=NoJaw())
    with pytest.raises(CompositionError, match="no move 'Crunch'"):
        _render(_ruleset(["carnivore", "strongjaw"]), names=NoCrunch())
