"""Redux Mode on Essentials 21 (#121): the generated file, run against stubs of Nova's classes."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from chrooked_pokedex.behavior import redux

pytestmark = pytest.mark.unit


def test_the_file_is_a_static_mod_with_the_shared_compose_runtime():
    text = redux.render_essentials21()
    assert text.startswith("# chrooked:zz_redux\n# mod-group: battle\n# mod-summary: ")
    assert "unless defined?(ChrookedCompose)" in text and "unless defined?(ChrookedLog)" in text
    assert "MenuHandlers.add(:options_menu, :chrooked_redux, {" in text
    assert text.endswith("end\n")


# Stubs with Nova's semantics (005_Event_Handlers.rb, 001_GameData.rb, 001_Battle_Battler.rb),
# then a Krookodile: Intimidate, Moxie, hidden Anger Point.
_PROBE = """
def _INTL(s); s; end
module MenuHandlers; def self.add(*); end; end
module PBEffects; Transform = 0; end
class HandlerHashSymbol
  def initialize; @hash = {}; end
  def [](sym)
    sym = sym.id if !sym.is_a?(Symbol) && sym.respond_to?("id")
    @hash[sym]
  end
  def add(sym, handler = nil, &block); @hash[sym] = handler || block; end
  def trigger(sym, *args)
    sym = sym.id if !sym.is_a?(Symbol) && sym.respond_to?("id")
    handler = self[sym]
    handler&.call(sym, *args)
  end
end
class AbilityHandlerHash < HandlerHashSymbol; end
module GameData
  class Ability
    attr_reader :id
    def initialize(id); @id = id; end
    def ==(other); other.is_a?(Symbol) ? @id == other : @id == other.id; end
    ALL = {}
    def self.exists?(id); ALL.key?(id); end
    def self.try_get(id); ALL[id]; end
  end
end
%i[INTIMIDATE MOXIE ANGERPOINT].each { |id| GameData::Ability::ALL[id] = GameData::Ability.new(id).freeze }
class Battle
  def initialize(*); end
  module AbilityEffects
    OnSwitchIn = AbilityHandlerHash.new
    OnEndOfUsingMove = AbilityHandlerHash.new
    SpeedCalc = AbilityHandlerHash.new
    def self.trigger(hash, *args, ret: false)
      r = hash.trigger(*args)
      r.nil? ? ret : r
    end
  end
  class Battler
    attr_accessor :ability_id, :effects
    def initialize(pokemon); @pokemon = pokemon; @ability_id = pokemon.ability_id; @effects = []; end
    def ability; GameData::Ability.try_get(@ability_id); end
    def abilityActive?(*); true; end
    def hasActiveAbility?(check, _ignore = false)
      return check.include?(@ability_id) if check.is_a?(Array)
      ability == check
    end
  end
end
Species = Struct.new(:abilities, :hidden_abilities)
Pokemon = Struct.new(:ability_id, :species_data)
class PokemonSystem; end
$PokemonSystem = PokemonSystem.new
__REDUX__
fired = []
Battle::AbilityEffects::OnSwitchIn.add(:INTIMIDATE, proc { |a, b| fired << a })
Battle::AbilityEffects::OnEndOfUsingMove.add(:MOXIE, proc { |a, b| fired << a })
Battle::AbilityEffects::SpeedCalc.add(:INTIMIDATE, proc { |a, b, m| m * 2 })
Battle::AbilityEffects::SpeedCalc.add(:MOXIE, proc { |a, b, m| m + 1 })
krook = Battle::Battler.new(Pokemon.new(:INTIMIDATE, Species.new([:INTIMIDATE, :MOXIE], [:ANGERPOINT])))
fx = Battle::AbilityEffects
show = lambda do
  fired.clear
  fx.trigger(fx::OnSwitchIn, krook.ability, krook)
  fx.trigger(fx::OnEndOfUsingMove, krook.ability, krook)
  speed = fx.trigger(fx::SpeedCalc, krook.ability, krook, 1, ret: 1)
  puts [fired.join("+"), speed, krook.hasActiveAbility?(:MOXIE), krook.hasActiveAbility?([:ANGERPOINT]),
        krook.ability == :INTIMIDATE].join(" ")
end
show.call
$PokemonSystem.chrooked_redux = 1
show.call
krook.ability_id = :MOXIE   # Skill Swap gave it Moxie alone
show.call
"""


@pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby not installed")
def test_a_redux_battler_fires_every_species_ability(tmp_path):
    probe = tmp_path / "probe.rb"
    probe.write_text(_PROBE.replace("__REDUX__", redux.render_essentials21()), encoding="utf-8")
    result = subprocess.run(["ruby", str(probe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "INTIMIDATE 2 false false true",              # Off: its own ability only
        "INTIMIDATE+MOXIE 3 true true true",         # On: Moxie fires too; speed threads (1*2)+1
        "MOXIE 2 true false false",                  # changed ability: that one alone
    ]
