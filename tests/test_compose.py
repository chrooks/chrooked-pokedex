"""Unit tests for composing a base Ruleset with a Target Override overlay."""

import pytest

from chrooked_pokedex.model.compose import (
    compose_ruleset,
    compose_species_override,
    overlay_touched_fields,
)
from chrooked_pokedex.model.ruleset import Ruleset
from chrooked_pokedex.model.schema import (
    AbilitiesOverride,
    MoveDef,
    SpeciesOverride,
    TypeChartOverride,
)


def _species(chrooked_id: str, **fields) -> SpeciesOverride:
    name = fields.pop("name", chrooked_id.title())
    return SpeciesOverride(name=name, chrooked_id=chrooked_id, **fields)


@pytest.mark.unit
def test_overlay_types_replace_base_types() -> None:
    base = _species("kricketune", types=("Bug", "Normal"))
    overlay = _species("kricketune", types=("Bug", "Fighting"))

    composed = compose_species_override(base, overlay)

    assert composed.types == ("Bug", "Fighting")


@pytest.mark.unit
def test_overlay_stats_merge_over_base_key_wise() -> None:
    base = _species("kricketune", stats={"atk": 80, "spe": 100})
    overlay = _species("kricketune", stats={"spe": 130})

    composed = compose_species_override(base, overlay)

    assert composed.stats == {"atk": 80, "spe": 130}


@pytest.mark.unit
def test_field_set_only_in_base_survives() -> None:
    base = _species("kricketune", types=("Bug", "Normal"), stats={"atk": 80})
    overlay = _species("kricketune", types=("Bug", "Fighting"))

    composed = compose_species_override(base, overlay)

    assert composed.stats == {"atk": 80}
    assert composed.types == ("Bug", "Fighting")


@pytest.mark.unit
def test_abilities_merge_slot_by_slot() -> None:
    base = _species("x", abilities=AbilitiesOverride(primary="Swarm", secondary="Technician"))
    overlay = _species("x", abilities=AbilitiesOverride(secondary="Sniper"))

    composed = compose_species_override(base, overlay)

    assert composed.abilities == AbilitiesOverride(primary="Swarm", secondary="Sniper")


@pytest.mark.unit
def test_overlay_stands_alone_when_no_base() -> None:
    overlay = _species("newmon", types=("Dragon",))

    composed = compose_species_override(None, overlay)

    assert composed is overlay


@pytest.mark.unit
def test_compose_ruleset_empty_overlay_is_identity() -> None:
    base = Ruleset(species={"kricketune": _species("kricketune", types=("Bug",))})

    assert compose_ruleset(base, None) is base
    composed = compose_ruleset(base, Ruleset())
    assert composed.species["kricketune"].types == ("Bug",)


@pytest.mark.unit
def test_compose_ruleset_overlays_species_and_keeps_base_only_entries() -> None:
    base = Ruleset(
        species={
            "kricketune": _species("kricketune", types=("Bug", "Normal")),
            "goodra": _species("goodra", types=("Dragon",)),
        }
    )
    overlay = Ruleset(species={"kricketune": _species("kricketune", types=("Bug", "Fighting"))})

    composed = compose_ruleset(base, overlay)

    assert composed.species["kricketune"].types == ("Bug", "Fighting")
    assert composed.species["goodra"].types == ("Dragon",)


@pytest.mark.unit
def test_compose_ruleset_moves_are_whole_entity_overlay_wins() -> None:
    base = Ruleset(
        moves={"tackle": MoveDef(name="Tackle", chrooked_id="tackle", type="Normal", category="physical", power=40)}
    )
    overlay = Ruleset(
        moves={"tackle": MoveDef(name="Tackle", chrooked_id="tackle", type="Normal", category="physical", power=55)}
    )

    composed = compose_ruleset(base, overlay)

    assert composed.moves["tackle"].power == 55


@pytest.mark.unit
def test_compose_ruleset_type_chart_cell_overlay_wins() -> None:
    base = Ruleset(type_chart=(TypeChartOverride("Bug", "Steel", 0.5),))
    overlay = Ruleset(type_chart=(TypeChartOverride("Bug", "Steel", 2.0),))

    composed = compose_ruleset(base, overlay)

    cells = {(c.attacker, c.defender): c.multiplier for c in composed.type_chart}
    assert cells[("Bug", "Steel")] == 2.0


@pytest.mark.unit
def test_overlay_touched_fields_lists_only_set_fields() -> None:
    overlay = _species("kricketune", types=("Bug", "Fighting"), stats={"spe": 130})

    assert overlay_touched_fields(overlay) == {"types", "stats"}
