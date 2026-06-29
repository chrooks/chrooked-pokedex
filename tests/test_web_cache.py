"""Read-cache behavior for the dex merge (#59) and the apply preview (#63).

Both prove the same shape with a deterministic hit/miss counter (no timing
flake): identical inputs → one compute then a hit; a changed input → a fresh
compute, never a stale result.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web import dex as dexmod
from chrooked_pokedex.web.app import create_app

_REPO = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO / "tests" / "fixtures" / "sample_ruleset"

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
    root = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, root)
    return root


@pytest.fixture
def snapshot_path(tmp_path: Path) -> Path:
    path = tmp_path / "1.11.2.json"
    path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    return path


@pytest.fixture
def client(ruleset_dir: Path, snapshot_path: Path, tmp_path: Path) -> TestClient:
    app = create_app(
        ruleset_dir=ruleset_dir,
        snapshot_path=snapshot_path,
        targets_path=tmp_path / "registry" / "targets.json",
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_dex_cache_hit_skips_rebuild(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}
    real = dexmod.build_dex

    def counting(snapshot, ruleset):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return real(snapshot, ruleset)

    monkeypatch.setattr(dexmod, "build_dex", counting)

    first = client.get("/api/dex").json()
    second = client.get("/api/dex").json()

    assert first == second
    assert calls["n"] == 1  # second request was a cache hit
    assert client.app.state.dex_cache_stats == {"hits": 1, "misses": 1}


@pytest.mark.unit
def test_dex_cache_recomputes_after_ruleset_edit(
    client: TestClient, ruleset_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}
    real = dexmod.build_dex

    def counting(snapshot, ruleset):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return real(snapshot, ruleset)

    monkeypatch.setattr(dexmod, "build_dex", counting)

    client.get("/api/dex")  # miss
    # Change Ruleset content -> a new fingerprint -> next read must recompute.
    (ruleset_dir / "meta.yaml").write_text(
        "base_version: 1.11.2\nschema_version: 1\n# edited\n", encoding="utf-8"
    )
    client.get("/api/dex")  # must NOT be served stale

    assert calls["n"] == 2
    assert client.app.state.dex_cache_stats == {"hits": 0, "misses": 2}
