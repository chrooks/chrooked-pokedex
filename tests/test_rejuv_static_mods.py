"""Per-Target static-mod switches: catalog headers, filtered install, the Mods API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chrooked_pokedex.appliers import static_mods
from chrooked_pokedex.appliers.rejuv.behavior_install import _DEFAULT_SOURCE_DIR
from chrooked_pokedex.model.mods import load_mods_off, write_mods_off
from chrooked_pokedex.report import ApplyReport
from chrooked_pokedex.sync import registry_entry_for_path
from chrooked_pokedex.web import mods as modsweb
from chrooked_pokedex.web.targets import Target, TargetError


def _mod(src: Path, mod_id: str, group: str = "convenience", extra: str = "") -> None:
    (src / f"chrooked_zz_{mod_id}.rb").write_text(
        f"# chrooked:zz_{mod_id}\n# mod-group: {group}\n# mod-summary: {mod_id} does a thing.\n"
        f"{extra}#\n# Longer notes.\nputs 1\n# not header\n",
        encoding="utf-8",
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    src = tmp_path / "harness"
    src.mkdir()
    _mod(src, "debug")
    _mod(src, "settime", extra="# mod-needs: debug\n")
    _mod(src, "redux", group="battle", extra="# mod-locked: other mods need its class\n")
    _mod(src, "pc")
    return src


def _by_id(report: ApplyReport) -> dict[str, tuple[str, str]]:
    return {e.chrooked_id: (e.status, e.reason) for e in report.entries}


@pytest.mark.unit
def test_every_real_harness_mod_declares_group_and_summary() -> None:
    # Guards the header Contract: a new chrooked_zz_ mod without its mod- lines
    # would break the catalog (and every apply) — this fails first.
    mods = static_mods.catalog(_DEFAULT_SOURCE_DIR)
    assert len(mods) >= 26
    ids = {m.id for m in mods}
    for mod in mods:
        assert all(need in ids for need in mod.needs), mod.id


@pytest.mark.unit
def test_header_parse(source: Path) -> None:
    mods = {m.id: m for m in static_mods.catalog(source)}
    assert mods["settime"].needs == ("debug",)
    assert mods["redux"].locked == "other mods need its class"
    assert "not header" not in mods["pc"].header
    assert mods["pc"].header.startswith("chrooked:zz_pc")


@pytest.mark.unit
def test_all_on_installs_everything_and_reports_nothing(tmp_path: Path, source: Path) -> None:
    report = ApplyReport()
    written = static_mods.install(tmp_path / "game", source, report)
    assert len(written) == 4
    assert report.entries == []


@pytest.mark.unit
def test_off_removes_the_installed_file_and_reports_held(tmp_path: Path, source: Path) -> None:
    game = tmp_path / "game"
    static_mods.install(game, source, ApplyReport())
    report = ApplyReport()
    static_mods.install(game, source, report, off=frozenset({"pc"}))
    assert not (game / "patch/Mods/chrooked_zz_pc.rb").exists()
    status, reason = _by_id(report)["pc"]
    assert status == "held" and "removed patch/Mods/chrooked_zz_pc.rb" in reason


@pytest.mark.unit
def test_mod_whose_need_is_off_is_blocked_not_installed(tmp_path: Path, source: Path) -> None:
    game = tmp_path / "game"
    report = ApplyReport()
    static_mods.install(game, source, report, off=frozenset({"debug"}))
    assert not (game / "patch/Mods/chrooked_zz_settime.rb").exists()
    status, reason = _by_id(report)["settime"]
    assert status == "blocked" and "needs debug" in reason


@pytest.mark.unit
def test_locked_mod_installs_even_when_off(tmp_path: Path, source: Path) -> None:
    game = tmp_path / "game"
    report = ApplyReport()
    static_mods.install(game, source, report, off=frozenset({"redux", "nosuchmod"}))
    assert (game / "patch/Mods/chrooked_zz_redux.rb").exists()
    entries = _by_id(report)
    assert entries["redux"][0] == "blocked"
    assert entries["nosuchmod"][0] == "blocked"


@pytest.mark.unit
def test_mods_yaml_round_trip(tmp_path: Path) -> None:
    assert load_mods_off(tmp_path, None) == frozenset()
    assert load_mods_off(tmp_path, "rejuv") == frozenset()
    write_mods_off(tmp_path, "rejuv", ["pc", "debug", "pc"])
    assert load_mods_off(tmp_path, "rejuv") == frozenset({"pc", "debug"})


@pytest.mark.unit
def test_registry_entry_for_path(tmp_path: Path) -> None:
    targets = tmp_path / "targets.json"
    targets.write_text(json.dumps([{"path": "/games/rejuv/", "namespace": "rejuv"}]))
    assert registry_entry_for_path(targets, Path("/games/rejuv"))["namespace"] == "rejuv"
    assert registry_entry_for_path(targets, Path("/games/other")) is None


def _client(ruleset_dir: Path, source: Path, namespace: str | None, engine: str = "rejuv") -> TestClient:
    target = Target(id="t1", label="Rejuvenation", path="/games/rejuv",
                    engine=engine, namespace=namespace)

    def get_target(target_id: str) -> Target:
        if target_id != "t1":
            raise TargetError(404, "no such target")
        return target

    app = FastAPI()
    app.include_router(modsweb.build_router(
        ruleset_dir=ruleset_dir, source_dir=source, get_target=get_target,
    ))
    return TestClient(app)


@pytest.mark.unit
def test_api_lists_catalog_with_target_switches(tmp_path: Path, source: Path) -> None:
    write_mods_off(tmp_path, "rejuv", ["pc"])
    body = _client(tmp_path, source, "rejuv").get("/api/mods?target=t1").json()
    assert {m["id"] for m in body["mods"]} == {"debug", "settime", "redux", "pc"}
    assert body["target"]["off"] == ["pc"] and body["target"]["supported"] is True


@pytest.mark.unit
def test_api_put_writes_file_and_ledger(tmp_path: Path, source: Path) -> None:
    response = _client(tmp_path, source, "rejuv").put(
        "/api/targets/t1/mods", json={"off": ["debug"]}
    )
    assert response.status_code == 200, response.text
    assert load_mods_off(tmp_path, "rejuv") == frozenset({"debug"})
    entry = json.loads((tmp_path / "ledger.ndjson").read_text().splitlines()[-1])
    assert entry["kind"] == "mods" and entry["to"] == ["debug"] and entry["scope"] == "target:rejuv"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("namespace", "off", "status"),
    [(None, ["pc"], 409), ("rejuv", ["nosuchmod"], 422), ("rejuv", ["redux"], 422)],
)
def test_api_put_rejects(tmp_path: Path, source: Path, namespace, off, status) -> None:
    client = _client(tmp_path, source, namespace)
    assert client.put("/api/targets/t1/mods", json={"off": off}).status_code == status
    assert not (tmp_path / "targets").exists()


@pytest.mark.unit
def test_api_gives_an_essentials_target_its_own_catalog(tmp_path: Path, source: Path) -> None:
    """Nova lists the generated Redux Mode (#121) plus the hand-written
    essentials21-harness chrooked_zz_*.rb mods, and each can be turned off."""
    client = _client(tmp_path, source, "nova", engine="essentials")
    body = client.get("/api/mods?target=t1").json()
    ids = [m["id"] for m in body["mods"]]
    assert body["engine"] == "essentials" and "redux" in ids and "pclevelall" in ids
    assert body["target"]["supported"] is True
    assert client.put("/api/targets/t1/mods", json={"off": ["redux"]}).status_code == 200
    assert load_mods_off(tmp_path, "nova") == frozenset({"redux"})


@pytest.mark.unit
def test_api_engine_without_mods_is_unsupported(tmp_path: Path, source: Path) -> None:
    client = _client(tmp_path, source, "pc", engine="pokeemerald")
    body = client.get("/api/mods?target=t1").json()
    assert body["engine"] == "rejuv" and body["target"]["supported"] is False
    assert client.put("/api/targets/t1/mods", json={"off": []}).status_code == 409
