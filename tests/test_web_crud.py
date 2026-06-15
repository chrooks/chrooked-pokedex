"""Milestone 2 slice 2a — CRUD for the three simple-record Ruleset kinds.

These drive the write endpoints (species / owned moves / owned abilities)
through Starlette's TestClient against a *writable copy* of the in-repo
`sample_ruleset` (so a write never dirties the committed fixture).

The contract under test:

- A save writes canonical YAML, then reloads it through the loader. A bad edit
  is rejected with HTTP 422 carrying the loader's own message, and **nothing is
  written** (the on-disk file is untouched).
- Deleting an owned move/ability a species still cites is blocked with HTTP 409
  until `?confirm=true`, and the 409 names the citing species.
- Deleting a species override just removes its file (reverts to base).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web.app import create_app

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"

_SNAPSHOT = {
    "version": "1.11.2",
    "species": {
        "goodra": {
            "dex": 706,
            "chrooked_id": "goodra",
            "name": "Goodra",
            "types": ["Dragon"],
            "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
            "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
            "learnset": [{"level": 1, "move": "Tackle"}],
        },
    },
    "moves": {},
    "abilities": {},
    "type_chart": [],
}


@pytest.fixture
def ruleset_dir(tmp_path: Path) -> Path:
    """A throwaway copy of the sample Ruleset so writes never touch the fixture."""
    dst = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, dst)
    return dst


@pytest.fixture
def client(ruleset_dir: Path, tmp_path: Path) -> TestClient:
    snap_path = tmp_path / "1.11.2.json"
    snap_path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(ruleset_dir=ruleset_dir, snapshot_path=snap_path)
    return TestClient(app, raise_server_exceptions=False)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Species
# --------------------------------------------------------------------------- #


def test_get_species_override_returns_overrides_only(client: TestClient) -> None:
    # Goodra's raw Override carries only the changed stat (spe), not all six —
    # the editor must load this, not the merged dex entry.
    response = client.get("/api/species/goodra")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stats"] == {"spe": 80}
    assert body["types"] == ["Water", "Dragon"]
    # learnset rides along so a save can't silently drop it
    assert any(m["move"] == "Excalibur" for m in body["learnset"])


def test_get_species_override_404_when_no_override(client: TestClient) -> None:
    response = client.get("/api/species/pikachu")
    assert response.status_code == 404


def test_put_species_writes_yaml_and_validates(
    client: TestClient, ruleset_dir: Path
) -> None:
    payload = {
        "name": "Goodra",
        "chrooked_id": "goodra",
        "aka": {"dex": 706, "pokeemerald": "SPECIES_GOODRA"},
        "types": ["Water", "Dragon"],
        "stats": {"spe": 99},
    }
    response = client.put("/api/species/goodra", json=payload)
    assert response.status_code == 200, response.text
    on_disk = _read(ruleset_dir / "species" / "goodra.yaml")
    assert "spe: 99" in on_disk
    # round-tripped value comes back so the UI can confirm what landed
    assert response.json()["stats"]["spe"] == 99


def test_put_species_creates_new_override_file(
    client: TestClient, ruleset_dir: Path
) -> None:
    payload = {
        "name": "Pikachu",
        "chrooked_id": "pikachu",
        "aka": {"dex": 25},
        "stats": {"spe": 120},
    }
    response = client.put("/api/species/pikachu", json=payload)
    assert response.status_code == 200, response.text
    assert (ruleset_dir / "species" / "pikachu.yaml").exists()


def test_put_species_invalid_stat_key_is_422_and_writes_nothing(
    client: TestClient, ruleset_dir: Path
) -> None:
    before = _read(ruleset_dir / "species" / "goodra.yaml")
    payload = {
        "name": "Goodra",
        "chrooked_id": "goodra",
        "stats": {"spee": 99},  # typo'd stat key
    }
    response = client.put("/api/species/goodra", json=payload)
    assert response.status_code == 422, response.text
    assert "spee" in response.json()["detail"]
    # write-nothing: the file on disk is byte-identical to before
    assert _read(ruleset_dir / "species" / "goodra.yaml") == before
    # no staging crumbs left behind
    assert not list((ruleset_dir / "species").glob(".staging*"))


def test_put_species_chrooked_id_mismatch_is_422(client: TestClient) -> None:
    payload = {"name": "Goodra", "chrooked_id": "not_goodra", "stats": {"spe": 99}}
    response = client.put("/api/species/goodra", json=payload)
    assert response.status_code == 422, response.text


def test_put_species_unknown_top_level_field_is_422(
    client: TestClient, ruleset_dir: Path
) -> None:
    before = _read(ruleset_dir / "species" / "goodra.yaml")
    payload = {"name": "Goodra", "chrooked_id": "goodra", "bogusfield": 1}
    response = client.put("/api/species/goodra", json=payload)
    assert response.status_code == 422, response.text
    assert "bogusfield" in response.json()["detail"]
    assert _read(ruleset_dir / "species" / "goodra.yaml") == before


def test_delete_species_removes_override_file(
    client: TestClient, ruleset_dir: Path
) -> None:
    assert (ruleset_dir / "species" / "goodra.yaml").exists()
    response = client.delete("/api/species/goodra")
    assert response.status_code == 200, response.text
    assert not (ruleset_dir / "species" / "goodra.yaml").exists()


def test_delete_species_404_when_absent(client: TestClient) -> None:
    response = client.delete("/api/species/missingno")
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Moves
# --------------------------------------------------------------------------- #


def test_put_move_creates_validated_file(
    client: TestClient, ruleset_dir: Path
) -> None:
    payload = {
        "name": "Holy Water",
        "chrooked_id": "holywater",
        "type": "Water",
        "category": "special",
        "power": 80,
        "accuracy": 100,
        "pp": 10,
        "description": "Blessed spray.",
    }
    response = client.put("/api/moves/holywater", json=payload)
    assert response.status_code == 200, response.text
    assert (ruleset_dir / "moves" / "holywater.yaml").exists()
    body = response.json()
    assert body["type"] == "Water"
    assert body["category"] == "special"


def test_put_move_invalid_category_is_422_and_writes_nothing(
    client: TestClient, ruleset_dir: Path
) -> None:
    payload = {
        "name": "Bad Move",
        "chrooked_id": "badmove",
        "type": "Water",
        "category": "bogus",
    }
    response = client.put("/api/moves/badmove", json=payload)
    assert response.status_code == 422, response.text
    assert "bogus" in response.json()["detail"]
    assert not (ruleset_dir / "moves" / "badmove.yaml").exists()


def test_put_move_invalid_flag_is_422(client: TestClient) -> None:
    payload = {
        "name": "Flaggy",
        "chrooked_id": "flaggy",
        "type": "Normal",
        "category": "physical",
        "flags": ["contact", "nonsense"],
    }
    response = client.put("/api/moves/flaggy", json=payload)
    assert response.status_code == 422, response.text
    assert "nonsense" in response.json()["detail"]


def test_put_move_missing_required_field_is_422(client: TestClient) -> None:
    payload = {"name": "No Category", "chrooked_id": "nocat", "type": "Normal"}
    response = client.put("/api/moves/nocat", json=payload)
    assert response.status_code == 422, response.text


def test_put_move_unknown_field_is_422(client: TestClient, ruleset_dir: Path) -> None:
    payload = {
        "name": "Odd",
        "chrooked_id": "odd",
        "type": "Normal",
        "category": "physical",
        "wattage": 9,  # not a move field
    }
    response = client.put("/api/moves/odd", json=payload)
    assert response.status_code == 422, response.text
    assert "wattage" in response.json()["detail"]
    assert not (ruleset_dir / "moves" / "odd.yaml").exists()


def test_delete_move_cited_by_learnset_is_blocked_until_confirmed(
    client: TestClient, ruleset_dir: Path
) -> None:
    # Goodra's learnset cites Excalibur in the sample fixture.
    response = client.delete("/api/moves/excalibur")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Goodra" in detail["citing"]
    # blocked = still on disk
    assert (ruleset_dir / "moves" / "excalibur.yaml").exists()


def test_delete_move_with_confirm_succeeds(
    client: TestClient, ruleset_dir: Path
) -> None:
    response = client.delete("/api/moves/excalibur?confirm=true")
    assert response.status_code == 200, response.text
    assert not (ruleset_dir / "moves" / "excalibur.yaml").exists()


def test_delete_uncited_move_succeeds_without_confirm(
    client: TestClient, ruleset_dir: Path
) -> None:
    # Create a move nothing cites, then delete it with no confirm.
    payload = {
        "name": "Holy Water",
        "chrooked_id": "holywater",
        "type": "Water",
        "category": "special",
    }
    assert client.put("/api/moves/holywater", json=payload).status_code == 200
    response = client.delete("/api/moves/holywater")
    assert response.status_code == 200, response.text
    assert not (ruleset_dir / "moves" / "holywater.yaml").exists()


def test_delete_move_404_when_absent(client: TestClient) -> None:
    response = client.delete("/api/moves/missing")
    assert response.status_code == 404


def test_editing_move_round_trips_aka(client: TestClient, ruleset_dir: Path) -> None:
    # The engine symbol in aka must survive a GET → edit → PUT cycle; dropping it
    # would quietly break apply (M3). The editor sends back the aka it received.
    move = next(m for m in client.get("/api/moves").json() if m["chrooked_id"] == "excalibur")
    move["power"] = 120
    response = client.put("/api/moves/excalibur", json=move)
    assert response.status_code == 200, response.text
    on_disk = _read(ruleset_dir / "moves" / "excalibur.yaml")
    assert "MOVE_EXCALIBUR" in on_disk
    assert "power: 120" in on_disk


# --------------------------------------------------------------------------- #
# Abilities
# --------------------------------------------------------------------------- #


def test_put_ability_creates_validated_file(
    client: TestClient, ruleset_dir: Path
) -> None:
    payload = {
        "name": "Aqua Veil",
        "chrooked_id": "aquaveil",
        "description": "Shields from burns.",
    }
    response = client.put("/api/abilities/aquaveil", json=payload)
    assert response.status_code == 200, response.text
    assert (ruleset_dir / "abilities" / "aquaveil.yaml").exists()
    assert response.json()["name"] == "Aqua Veil"


def test_put_ability_unknown_field_is_422_and_writes_nothing(
    client: TestClient, ruleset_dir: Path
) -> None:
    payload = {
        "name": "Aqua Veil",
        "chrooked_id": "aquaveil",
        "potency": 5,  # not an allowed ability field
    }
    response = client.put("/api/abilities/aquaveil", json=payload)
    assert response.status_code == 422, response.text
    assert "potency" in response.json()["detail"]
    assert not (ruleset_dir / "abilities" / "aquaveil.yaml").exists()


def test_delete_ability_cited_by_species_is_blocked_until_confirmed(
    client: TestClient, ruleset_dir: Path
) -> None:
    # Goodra's primary ability is Poison Heal in the sample fixture.
    response = client.delete("/api/abilities/poisonheal")
    assert response.status_code == 409, response.text
    assert "Goodra" in response.json()["detail"]["citing"]
    assert (ruleset_dir / "abilities" / "poisonheal.yaml").exists()


def test_delete_ability_with_confirm_succeeds(
    client: TestClient, ruleset_dir: Path
) -> None:
    response = client.delete("/api/abilities/poisonheal?confirm=true")
    assert response.status_code == 200, response.text
    assert not (ruleset_dir / "abilities" / "poisonheal.yaml").exists()


def test_editing_ability_round_trips_aka(
    client: TestClient, ruleset_dir: Path
) -> None:
    entry = next(
        a for a in client.get("/api/abilities").json() if a["chrooked_id"] == "poisonheal"
    )
    # The merged AbilityEntry carries display-only fields (`overridden_fields`,
    # `base`); the editor sends back only the writable AbilityDef fields. Mirror
    # that here so the PUT round-trips like the real client.
    ability = {
        "name": entry["name"],
        "chrooked_id": entry["chrooked_id"],
        "description": "Now heals more.",
        "aka": entry["aka"],
    }
    response = client.put("/api/abilities/poisonheal", json=ability)
    assert response.status_code == 200, response.text
    on_disk = _read(ruleset_dir / "abilities" / "poisonheal.yaml")
    assert "ABILITY_POISON_HEAL" in on_disk


# --------------------------------------------------------------------------- #
# Type chart (a single whole-list file: type-chart/overrides.yaml)
# --------------------------------------------------------------------------- #


def test_put_type_chart_replaces_overrides(
    client: TestClient, ruleset_dir: Path
) -> None:
    entries = [
        {"attacker": "Water", "defender": "Fire", "multiplier": 2},
        {"attacker": "Fire", "defender": "Water", "multiplier": 0.5},
    ]
    response = client.put("/api/type-chart", json=entries)
    assert response.status_code == 200, response.text
    on_disk = _read(ruleset_dir / "type-chart" / "overrides.yaml")
    assert "attacker: Water" in on_disk
    # the original Flying/Ice override is gone (whole-list replace)
    assert "Flying" not in on_disk
    assert {"attacker": "Water", "defender": "Fire", "multiplier": 2.0} in (
        client.get("/api/type-chart").json()
    )


def test_put_type_chart_invalid_multiplier_is_422_writes_nothing(
    client: TestClient, ruleset_dir: Path
) -> None:
    before = _read(ruleset_dir / "type-chart" / "overrides.yaml")
    entries = [{"attacker": "Water", "defender": "Fire", "multiplier": "lots"}]
    response = client.put("/api/type-chart", json=entries)
    assert response.status_code == 422, response.text
    assert _read(ruleset_dir / "type-chart" / "overrides.yaml") == before


def test_put_type_chart_unknown_field_is_422(client: TestClient) -> None:
    entries = [{"attacker": "Water", "defender": "Fire", "multiplier": 2, "x": 1}]
    response = client.put("/api/type-chart", json=entries)
    assert response.status_code == 422, response.text
    assert "x" in response.json()["detail"]


def test_put_type_chart_can_clear_to_empty(
    client: TestClient, ruleset_dir: Path
) -> None:
    response = client.put("/api/type-chart", json=[])
    assert response.status_code == 200, response.text
    assert client.get("/api/type-chart").json() == []


# --------------------------------------------------------------------------- #
# Behaviors (human-owned; need their own YAML renderer)
# --------------------------------------------------------------------------- #


def _behavior_payload() -> dict:
    return {
        "name": "Aqua Boost",
        "chrooked_id": "aquaboost",
        "applies_to": "ability",
        "aka": {"pokeemerald": "ABILITY_AQUA_BOOST"},
        "effects": [
            {
                "summary": "Boosts Water moves in rain.",
                "trigger": "damage-calc",
                "effect": "multiply Water-move damage by 1.3",
                "when": "it is raining",
            }
        ],
        "test_cases": [
            {"given": "a Water move is used in rain", "expect": "1.3x damage"}
        ],
        "notes": ["Stacks multiplicatively with other rain boosts."],
        "engine_hints": {"pokeemerald": "see ABILITY_AQUA_BOOST"},
    }


def test_put_behavior_creates_validated_file(
    client: TestClient, ruleset_dir: Path
) -> None:
    response = client.put("/api/behaviors/aquaboost", json=_behavior_payload())
    assert response.status_code == 200, response.text
    assert (ruleset_dir / "behaviors" / "aquaboost.yaml").exists()
    body = response.json()
    assert body["applies_to"] == "ability"
    assert body["effects"][0]["trigger"] == "damage-calc"


def test_put_behavior_invalid_trigger_is_422_writes_nothing(
    client: TestClient, ruleset_dir: Path
) -> None:
    payload = _behavior_payload()
    payload["effects"][0]["trigger"] = "bogus-trigger"
    response = client.put("/api/behaviors/aquaboost", json=payload)
    assert response.status_code == 422, response.text
    assert "bogus-trigger" in response.json()["detail"]
    assert not (ruleset_dir / "behaviors" / "aquaboost.yaml").exists()


def test_put_behavior_requires_an_effect_422(client: TestClient) -> None:
    payload = _behavior_payload()
    payload["effects"] = []
    response = client.put("/api/behaviors/aquaboost", json=payload)
    assert response.status_code == 422, response.text


def test_editing_behavior_round_trips_aka(
    client: TestClient, ruleset_dir: Path
) -> None:
    behavior = next(
        b for b in client.get("/api/behaviors").json() if b["chrooked_id"] == "excalibur"
    )
    behavior["notes"] = ["Edited note."]
    response = client.put("/api/behaviors/excalibur", json=behavior)
    assert response.status_code == 200, response.text
    on_disk = _read(ruleset_dir / "behaviors" / "excalibur.yaml")
    assert "MOVE_EXCALIBUR" in on_disk
    assert "Edited note." in on_disk


def test_delete_behavior_removes_file(
    client: TestClient, ruleset_dir: Path
) -> None:
    assert (ruleset_dir / "behaviors" / "excalibur.yaml").exists()
    response = client.delete("/api/behaviors/excalibur")
    assert response.status_code == 200, response.text
    assert not (ruleset_dir / "behaviors" / "excalibur.yaml").exists()


def test_delete_behavior_404_when_absent(client: TestClient) -> None:
    response = client.delete("/api/behaviors/missing")
    assert response.status_code == 404
