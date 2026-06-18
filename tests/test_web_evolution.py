"""The pure evolution-graph transform that feeds the snapshot.

`web/evolution.build_evolution_graph` turns the parser's forward edges
(`{SPECIES_X: [EvolutionEntry(...)]}`) into the two per-species fields the
snapshot stores: forward `evolves_into` (branching-safe list) and the inverted
backward `evolution.from` (each target's single pre-evo). These tests are
hermetic — they feed synthetic `EvolutionEntry` rows and a name resolver, no
base checkout.
"""

from __future__ import annotations

from chrooked_pokedex.readers.pokeemerald.evolution_parser import EvolutionEntry
from chrooked_pokedex.web import evolution as evo


def _resolver() -> evo.SpeciesResolver:
    # Map the SPECIES_* symbols the tests use to (chrooked_id, display name, dex).
    table: dict[str, tuple[str, str, int | None]] = {
        "SPECIES_BUIZEL": ("buizel", "Buizel", 418),
        "SPECIES_FLOATZEL": ("floatzel", "Floatzel", 419),
        "SPECIES_EEVEE": ("eevee", "Eevee", 133),
        "SPECIES_VAPOREON": ("vaporeon", "Vaporeon", 134),
        "SPECIES_JOLTEON": ("jolteon", "Jolteon", 135),
        "SPECIES_FLAREON": ("flareon", "Flareon", 136),
    }
    return lambda symbol: table.get(symbol)


def test_linear_chain_fills_both_directions() -> None:
    graph = evo.build_evolution_graph(
        {"SPECIES_BUIZEL": [EvolutionEntry("EVO_LEVEL", "26", "SPECIES_FLOATZEL")]},
        _resolver(),
    )

    # Forward edge on the source.
    buizel = graph["buizel"]
    assert buizel["evolves_into"] == [
        {
            "to": "floatzel",
            "to_name": "Floatzel",
            "to_dex": 419,
            "method": "Level 26",
            "method_detail": {"kind": "EVO_LEVEL", "param": "26"},
        }
    ]
    assert buizel["evolution"] is None  # no pre-evo for Buizel

    # Inverted backward edge on the target.
    floatzel = graph["floatzel"]
    assert floatzel["evolution"] == {
        "from": "buizel",
        "from_name": "Buizel",
        "from_dex": 418,
        "method": "Level 26",
        "method_detail": {"kind": "EVO_LEVEL", "param": "26"},
    }
    assert floatzel["evolves_into"] == []  # Floatzel is a final form


def test_branching_lists_multiple_targets() -> None:
    graph = evo.build_evolution_graph(
        {
            "SPECIES_EEVEE": [
                EvolutionEntry("EVO_ITEM", "ITEM_WATER_STONE", "SPECIES_VAPOREON"),
                EvolutionEntry("EVO_ITEM", "ITEM_THUNDER_STONE", "SPECIES_JOLTEON"),
                EvolutionEntry("EVO_ITEM", "ITEM_FIRE_STONE", "SPECIES_FLAREON"),
            ]
        },
        _resolver(),
    )

    eevee = graph["eevee"]
    assert [
        {"to": e["to"], "to_name": e["to_name"], "method": e["method"]}
        for e in eevee["evolves_into"]
    ] == [
        {"to": "vaporeon", "to_name": "Vaporeon", "method": "Water Stone"},
        {"to": "jolteon", "to_name": "Jolteon", "method": "Thunder Stone"},
        {"to": "flareon", "to_name": "Flareon", "method": "Fire Stone"},
    ]
    # Each target gets Eevee as its single pre-evo.
    assert graph["vaporeon"]["evolution"]["from"] == "eevee"
    assert graph["jolteon"]["evolution"]["from_name"] == "Eevee"
    assert graph["flareon"]["evolution"]["method"] == "Fire Stone"


def test_unresolvable_target_is_skipped() -> None:
    # A SPECIES_* the resolver can't place (e.g. a Gigantamax form dropped from
    # the snapshot) must not crash or emit a half-edge.
    graph = evo.build_evolution_graph(
        {"SPECIES_BUIZEL": [EvolutionEntry("EVO_LEVEL", "26", "SPECIES_UNKNOWN")]},
        _resolver(),
    )
    assert graph == {}


def test_multiple_pre_evos_picks_deterministically() -> None:
    # If two sources both evolve into the same target (rare/pathological), the
    # inverted `from` is deterministic — the first source by chrooked_id.
    graph = evo.build_evolution_graph(
        {
            "SPECIES_JOLTEON": [EvolutionEntry("EVO_LEVEL", "1", "SPECIES_FLAREON")],
            "SPECIES_EEVEE": [EvolutionEntry("EVO_LEVEL", "1", "SPECIES_FLAREON")],
        },
        _resolver(),
    )
    # "eevee" < "jolteon" lexicographically, so it wins the single `from` slot.
    assert graph["flareon"]["evolution"]["from"] == "eevee"


def test_method_label_humanizes_common_kinds() -> None:
    assert evo.method_label("EVO_LEVEL", "26") == "Level 26"
    assert evo.method_label("EVO_ITEM", "ITEM_WATER_STONE") == "Water Stone"
    assert evo.method_label("EVO_FRIENDSHIP", "0") == "Friendship"
    assert evo.method_label("EVO_TRADE", "0") == "Trade"
    assert evo.method_label("EVO_LEVEL_NINJASK", "20") == "Level Ninjask 20"


def test_structured_method_rides_along() -> None:
    graph = evo.build_evolution_graph(
        {"SPECIES_BUIZEL": [EvolutionEntry("EVO_LEVEL", "26", "SPECIES_FLOATZEL")]},
        _resolver(),
    )
    # The readable label is what the UI shows; the structured form rides along for
    # a faithful round-trip if the API ever needs it.
    edge = graph["buizel"]["evolves_into"][0]
    assert edge["method"] == "Level 26"
    assert edge["method_detail"] == {"kind": "EVO_LEVEL", "param": "26"}
