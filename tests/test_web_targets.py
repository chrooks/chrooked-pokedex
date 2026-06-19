"""Milestone 3 — Targets, preview, and apply (backend).

One test per acceptance criterion (ac1–ac8). The git-safety criteria (ac2, ac4,
ac6) drive controlled file changes over a dummy git repo — some via a monkeypatched
applier so the change is deterministic. The honest-applier criteria (ac3, ac5,
ac7, ac8) run the REAL pokeemerald applier over a minimal hand-built git fork,
mirroring the fixture style of `test_creation.py` / `test_tier_integration.py`.

The fork is a real git repo committed clean, so the clean-tree gate holds and
`git clean -fd` removes exactly the applier-created files (D1).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web import targets as targetsmod
from chrooked_pokedex.web.app import create_app

_REPO_ROOT = Path(__file__).resolve().parent.parent

_SNAPSHOT = {
    "version": "1.11.2",
    "species": {
        "aegislash": {
            "dex": 681,
            "chrooked_id": "aegislash",
            "name": "Aegislash",
            "types": ["Steel", "Ghost"],
            "abilities": {
                "primary": "Stance Change",
                "secondary": None,
                "hidden": None,
            },
            # Base snapshot HP differs from the fork's own value (60) so the
            # per-Target backdrop can show the fork value, proving the backdrop
            # reads the fork, not the committed base.
            "stats": {"hp": 99, "atk": 50, "def": 50, "spa": 50, "spd": 50, "spe": 50},
            "learnset": [{"level": 1, "move": "Tackle"}],
        },
    },
    "moves": {},
    "abilities": {},
    "type_chart": [],
}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


def _init_committed_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fork base")


def _write_minimal_fork(target: Path) -> None:
    """A minimal but real pokeemerald fork the applier can actually apply to.

    Carries one species (Aegislash, HP=60), its learnset, and the move/ability
    symbol tables the resolution map and creation tier read. The Ruleset below
    creates a DATA-ONLY ability (Striker) the fork lacks.
    """
    pokemon = target / "src" / "data" / "pokemon"
    (pokemon / "level_up_learnsets").mkdir(parents=True)
    (target / "include" / "constants").mkdir(parents=True)

    (pokemon / "level_up_learnsets" / "gen_1.h").write_text(
        "static const struct LevelUpMove sAegislashLevelUpLearnset[] = {\n"
        "    LEVEL_UP_MOVE(1, MOVE_TACKLE),\n"
        "    LEVEL_UP_END\n"
        "};\n",
        encoding="utf-8",
    )
    (pokemon / "species_info.h").write_text(
        "    [SPECIES_AEGISLASH] =\n"
        "    {\n"
        "        .baseHP = 60,\n"
        "        .baseAttack = 50,\n"
        "        .levelUpLearnset = sAegislashLevelUpLearnset,\n"
        "    },\n",
        encoding="utf-8",
    )
    (target / "src" / "data" / "moves_info.h").write_text(
        "const struct MoveInfo gMovesInfo[MOVES_COUNT] =\n"
        "{\n"
        '    [MOVE_TACKLE] = { .name = COMPOUND_STRING("Tackle"), '
        ".type = TYPE_NORMAL, .category = DAMAGE_CATEGORY_PHYSICAL, },\n"
        "};\n",
        encoding="utf-8",
    )
    (target / "include" / "constants" / "moves.h").write_text(
        "#define MOVE_NONE 0\n"
        "#define MOVE_TACKLE 1\n"
        "#define MOVES_COUNT_GEN9 2\n"
        "#define MOVES_COUNT MOVES_COUNT_GEN9\n",
        encoding="utf-8",
    )
    (target / "include" / "constants" / "abilities.h").write_text(
        "#define ABILITY_NONE 0\n"
        "#define ABILITY_STENCH 1\n"
        "#define ABILITIES_COUNT_GEN9 2\n"
        "#define ABILITIES_COUNT ABILITIES_COUNT_GEN9\n",
        encoding="utf-8",
    )
    (target / "src" / "data" / "abilities.h").write_text(
        "const struct AbilityInfo gAbilitiesInfo[ABILITIES_COUNT] =\n"
        "{\n"
        "    [ABILITY_STENCH] =\n"
        "    {\n"
        '        .name = _("Stench"),\n'
        '        .description = COMPOUND_STRING("Repels."),\n'
        "    },\n"
        "};\n",
        encoding="utf-8",
    )
    # A tiny 2x2 type matrix so the per-Target type-chart backdrop has a real fork
    # grid to merge the Ruleset onto (Fire super-effective on Grass = 2.0 here).
    (target / "src" / "data" / "types_info.h").write_text(
        "const uq4_12_t gTypeEffectivenessTable"
        "[NUMBER_OF_MON_TYPES][NUMBER_OF_MON_TYPES] =\n"
        "{//                 Fire    Grass\n"
        "    [TYPE_FIRE]  = {______, X(2.0)},\n"
        "    [TYPE_GRASS] = {X(0.5), ______},\n"
        "};\n",
        encoding="utf-8",
    )


def _write_ruleset(root: Path) -> None:
    """A Ruleset that changes Aegislash HP and owns a behavior-backed ability.

    The Striker ability is absent from the fork, so the creation tier creates it;
    because a behavior spec exists for it, the report marks it DATA ONLY (ac8).
    """
    (root / "species").mkdir(parents=True)
    (root / "abilities").mkdir(parents=True)
    (root / "moves").mkdir(parents=True)
    (root / "behaviors").mkdir(parents=True)
    (root / "type-chart").mkdir(parents=True)
    # One type-chart override the fork's 2x2 grid has a base cell for, so the
    # backdrop merge flags it overridden with the fork's own base_multiplier.
    (root / "type-chart" / "overrides.yaml").write_text(
        "overrides:\n  - { attacker: Fire, defender: Grass, multiplier: 0.5 }\n",
        encoding="utf-8",
    )
    (root / "meta.yaml").write_text(
        "base_version: 1.11.2\nschema_version: 1\n", encoding="utf-8"
    )
    (root / "species" / "aegislash.yaml").write_text(
        "name: Aegislash\n"
        "chrooked_id: aegislash\n"
        "aka: { pokeemerald: SPECIES_AEGISLASH }\n"
        "stats: { hp: 140 }\n",
        encoding="utf-8",
    )
    # An owned move the fork lacks -> surfaced as a created move in the backdrop.
    (root / "moves" / "excalibur.yaml").write_text(
        "name: Excalibur\n"
        "chrooked_id: excalibur\n"
        "aka: { pokeemerald: MOVE_EXCALIBUR }\n"
        "type: Steel\n"
        "category: physical\n"
        "power: 90\n"
        "accuracy: 100\n"
        "pp: 10\n"
        "description: A holy sword strike.\n",
        encoding="utf-8",
    )
    (root / "abilities" / "striker.yaml").write_text(
        "name: Striker\n"
        "chrooked_id: striker\n"
        "aka: { pokeemerald: ABILITY_STRIKER }\n"
        "description: Boosts kicking moves.\n",
        encoding="utf-8",
    )
    (root / "behaviors" / "striker.yaml").write_text(
        "name: Striker\n"
        "chrooked_id: striker\n"
        "applies_to: ability\n"
        "effects:\n"
        "  - summary: Boosts kicking moves by 30%.\n"
        "    trigger: damage-calc\n"
        "    effect: Multiplies kicking-move power by 1.3.\n"
        "    when: the user has Striker\n"
        "test_cases:\n"
        "  - given: a kicking move is used\n"
        "    expect: power is multiplied by 1.3\n",
        encoding="utf-8",
    )


@pytest.fixture
def snapshot_path(tmp_path: Path) -> Path:
    path = tmp_path / "1.11.2.json"
    path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    return path


@pytest.fixture
def ruleset_dir(tmp_path: Path) -> Path:
    root = tmp_path / "ruleset"
    _write_ruleset(root)
    return root


@pytest.fixture
def targets_path(tmp_path: Path) -> Path:
    return tmp_path / "registry" / "targets.json"


@pytest.fixture
def client(snapshot_path: Path, ruleset_dir: Path, targets_path: Path) -> TestClient:
    app = create_app(
        ruleset_dir=ruleset_dir,
        snapshot_path=snapshot_path,
        targets_path=targets_path,
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def fork(tmp_path: Path) -> Path:
    """A real, committed-clean minimal pokeemerald git fork."""
    path = tmp_path / "fork"
    _write_minimal_fork(path)
    _init_committed_repo(path)
    return path


def _register(client: TestClient, fork: Path) -> str:
    response = client.post(
        "/api/targets",
        json={"label": "Test Fork", "path": str(fork), "engine": "pokeemerald"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


# --- ac1: registry CRUD round-trips to the injected targets.json ----------- #


def test_ac1_registry_crud_round_trip(
    client: TestClient, fork: Path, targets_path: Path
) -> None:
    # add
    add = client.post(
        "/api/targets",
        json={"label": "My Fork", "path": str(fork), "engine": "pokeemerald"},
    )
    assert add.status_code == 200, add.text
    body = add.json()
    target_id = body["id"]
    assert body["label"] == "My Fork"
    assert body["engine"] == "pokeemerald"
    # path stored ABSOLUTE
    assert Path(body["path"]).is_absolute()
    assert Path(body["path"]) == fork.resolve()

    # file persisted at the injected path
    assert targets_path.exists()
    on_disk = json.loads(targets_path.read_text(encoding="utf-8"))
    assert any(row["id"] == target_id for row in on_disk)
    assert Path(on_disk[0]["path"]).is_absolute()

    # list
    listed = client.get("/api/targets").json()
    assert [t["id"] for t in listed] == [target_id]

    # delete
    deleted = client.delete(f"/api/targets/{target_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": target_id}
    assert client.get("/api/targets").json() == []

    # delete unknown -> 404
    assert client.delete("/api/targets/nope").status_code == 404


def test_ac1_add_rejects_non_git_path(client: TestClient, tmp_path: Path) -> None:
    plain = tmp_path / "not_a_repo"
    plain.mkdir()
    response = client.post(
        "/api/targets",
        json={"label": "x", "path": str(plain), "engine": "pokeemerald"},
    )
    assert response.status_code == 422


# --- ac2: preview refuses a dirty tree (409); fork untouched --------------- #


def test_ac2_preview_dirty_tree_409(client: TestClient, fork: Path) -> None:
    (fork / "dirt.txt").write_text("uncommitted\n", encoding="utf-8")
    before = subprocess.run(
        ["git", "-C", str(fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout

    target_id = _register(client, fork)
    response = client.post(f"/api/targets/{target_id}/preview")
    assert response.status_code == 409
    assert "uncommitted" in response.json()["detail"].lower()

    after = subprocess.run(
        ["git", "-C", str(fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout
    assert before == after  # fork left untouched


# --- ac3: preview on a clean fork runs the real applier and restores ------- #


def test_ac3_preview_clean_runs_real_applier_and_restores(
    client: TestClient, fork: Path
) -> None:
    target_id = _register(client, fork)
    response = client.post(f"/api/targets/{target_id}/preview")
    assert response.status_code == 200, response.text
    body = response.json()
    # real Apply Report counts present; the applier created the Striker ability.
    assert body["applied"] >= 1
    assert {"applied", "partial", "blocked", "created", "data_only"} <= set(body)
    assert body["created"] >= 1

    # fork restored to clean; applier-created files gone.
    porcelain = subprocess.run(
        ["git", "-C", str(fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert porcelain == "", f"fork not clean after preview: {porcelain!r}"


# --- ac4: restore is crash-safe; failed restore -> loud 500 + recovery ----- #


def test_ac4_restore_runs_even_when_applier_raises(
    client: TestClient, fork: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_id = _register(client, fork)

    def boom(target, engine, ruleset):  # noqa: ANN001
        # Simulate a mid-run crash AFTER touching a file, to prove finally restores.
        (Path(target) / "half_written.h").write_text("partial\n", encoding="utf-8")
        raise RuntimeError("applier exploded mid-run")

    monkeypatch.setattr(targetsmod, "_run_applier", boom)
    response = client.post(f"/api/targets/{target_id}/preview")
    assert response.status_code == 500  # the crash surfaces

    # finally ran the restore: the half-written file is gone, tree clean.
    assert not (fork / "half_written.h").exists()
    porcelain = subprocess.run(
        ["git", "-C", str(fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert porcelain == ""


def test_ac4_failed_restore_500_with_recovery_command(
    client: TestClient, fork: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_id = _register(client, fork)

    def bad_restore(target):  # noqa: ANN001
        raise targetsmod.RestoreError(
            500,
            {
                "message": "Restore failed.",
                "recovery": (
                    f"git -C {target} checkout -- . && git -C {target} clean -fd"
                ),
            },
        )

    monkeypatch.setattr(targetsmod, "restore_fork_to_clean", bad_restore)
    response = client.post(f"/api/targets/{target_id}/preview")
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "checkout -- ." in detail["recovery"]
    assert "clean -fd" in detail["recovery"]
    # The real applier ran but the (patched) restore was skipped, so the fork is
    # left dirty here — exactly the failure the recovery command addresses. Clean
    # it up with raw git (the patched restore_fork_to_clean would re-raise).
    monkeypatch.undo()
    subprocess.run(["git", "-C", str(fork), "checkout", "--", "."], check=True)
    subprocess.run(["git", "-C", str(fork), "clean", "-fd"], check=True)


# --- restore gates on git return codes (review fix #1) --------------------- #


def test_restore_raises_on_nonzero_checkout_even_if_tree_reads_clean(
    fork: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-zero checkout returncode must raise even if porcelain reads clean.

    The fork is already committed-clean, so ``git status --porcelain`` returns
    empty — the old final-backstop check alone would pass. We force the checkout
    subprocess to report a non-zero returncode (leaving the clean and status calls
    real), proving the new returncode gate fires before the backstop is reached.
    """
    real_run = subprocess.run

    def fake_run(args, *a, **kw):  # noqa: ANN001, ANN002, ANN003
        completed = real_run(args, *a, **kw)
        # Only sabotage the checkout step; let clean + status run for real.
        if "checkout" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout="",
                stderr="fatal: simulated checkout failure",
            )
        return completed

    monkeypatch.setattr(targetsmod.subprocess, "run", fake_run)

    with pytest.raises(targetsmod.RestoreError) as caught:
        targetsmod.restore_fork_to_clean(fork)

    detail = caught.value.detail
    assert detail["failed_step"] == "checkout"
    assert "checkout -- ." in detail["recovery"]
    assert "simulated checkout failure" in detail["stderr"]

    # the tree itself is genuinely clean (the gate fired on returncode, not dirt).
    porcelain = real_run(
        ["git", "-C", str(fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert porcelain == ""


# --- ac5: apply keeps files; counts match a preceding preview -------------- #


def test_ac5_apply_matches_preview_and_changes_files(
    client: TestClient, fork: Path
) -> None:
    target_id = _register(client, fork)
    preview = client.post(f"/api/targets/{target_id}/preview").json()

    apply = client.post(f"/api/targets/{target_id}/apply", json={})
    assert apply.status_code == 200, apply.text
    applied = apply.json()
    for key in ("applied", "partial", "blocked", "created"):
        assert applied[key] == preview[key], key

    # files changed on disk and KEPT after apply.
    porcelain = subprocess.run(
        ["git", "-C", str(fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert porcelain != "", "apply should leave the fork dirty (changes kept)"

    # the Apply Report sidecar is written to disk, not just returned in counts.
    assert (fork / "apply-report.md").exists()


# --- ac6: apply refuses dirty without force; proceeds with force ----------- #


def test_ac6_apply_dirty_requires_force(client: TestClient, fork: Path) -> None:
    (fork / "dirt.txt").write_text("uncommitted\n", encoding="utf-8")
    target_id = _register(client, fork)

    no_force = client.post(f"/api/targets/{target_id}/apply", json={})
    assert no_force.status_code == 409

    forced = client.post(f"/api/targets/{target_id}/apply", json={"force": True})
    assert forced.status_code == 200, forced.text
    porcelain = subprocess.run(
        ["git", "-C", str(fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert porcelain != ""


# --- ac7: per-Target dex backdrop reads the fork; snapshot cached ---------- #


def test_ac7_target_dex_backdrop_and_snapshot_cache(
    client: TestClient, fork: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_id = _register(client, fork)

    # spy on build_snapshot to prove it runs once across two dex requests.
    calls = {"n": 0}
    real_build = targetsmod.snapmod.build_snapshot

    def counting_build(base_dir):  # noqa: ANN001
        calls["n"] += 1
        return real_build(base_dir)

    monkeypatch.setattr(targetsmod.snapmod, "build_snapshot", counting_build)

    first = client.get(f"/api/targets/{target_id}/dex")
    assert first.status_code == 200, first.text
    second = client.get(f"/api/targets/{target_id}/dex")
    assert second.status_code == 200

    assert calls["n"] == 1, "snapshot should be built once and cached"

    # backdrop merges Ruleset (hp:140) onto the FORK's own value, not base (99).
    entry = next(e for e in first.json() if e["chrooked_id"] == "aegislash")
    assert entry["stats"]["hp"] == 140  # Ruleset override
    assert entry["base"]["stats"]["hp"] == 60  # the FORK's own value, not base 99


# --- abilities slice ac4: per-Target abilities backdrop; snapshot cached --- #


def test_abilities_ac4_target_backdrop_and_snapshot_cache(
    client: TestClient, fork: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_id = _register(client, fork)

    # spy on build_snapshot to prove it runs once across two abilities requests.
    calls = {"n": 0}
    real_build = targetsmod.snapmod.build_snapshot

    def counting_build(base_dir):  # noqa: ANN001
        calls["n"] += 1
        return real_build(base_dir)

    monkeypatch.setattr(targetsmod.snapmod, "build_snapshot", counting_build)

    first = client.get(f"/api/targets/{target_id}/abilities")
    assert first.status_code == 200, first.text
    second = client.get(f"/api/targets/{target_id}/abilities")
    assert second.status_code == 200

    assert calls["n"] == 1, "snapshot should be built once and cached"

    abilities = first.json()
    ids = {a["chrooked_id"] for a in abilities}
    # The fork's own ability (Stench) rides along as base-only (unflagged).
    assert "stench" in ids
    stench = next(a for a in abilities if a["chrooked_id"] == "stench")
    assert stench["overridden_fields"] == []
    # The Ruleset owns Striker, which the fork lacks -> surfaced as created.
    assert "striker" in ids
    striker = next(a for a in abilities if a["chrooked_id"] == "striker")
    assert striker["base"] == {}
    assert set(striker["overridden_fields"]) == {"name", "description"}


# --- moves slice ac4: per-Target moves backdrop; snapshot cached ----------- #


def test_moves_ac4_target_backdrop_and_snapshot_cache(
    client: TestClient, fork: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_id = _register(client, fork)

    # spy on build_snapshot to prove it runs once across two moves requests.
    calls = {"n": 0}
    real_build = targetsmod.snapmod.build_snapshot

    def counting_build(base_dir):  # noqa: ANN001
        calls["n"] += 1
        return real_build(base_dir)

    monkeypatch.setattr(targetsmod.snapmod, "build_snapshot", counting_build)

    first = client.get(f"/api/targets/{target_id}/moves")
    assert first.status_code == 200, first.text
    second = client.get(f"/api/targets/{target_id}/moves")
    assert second.status_code == 200

    assert calls["n"] == 1, "snapshot should be built once and cached"

    moves = first.json()
    ids = {m["chrooked_id"] for m in moves}
    # The fork's own move (Tackle) rides along as base-only (unflagged), neutral.
    assert "tackle" in ids
    tackle = next(m for m in moves if m["chrooked_id"] == "tackle")
    assert tackle["overridden_fields"] == []
    assert tackle["type"] == "Normal"  # neutral, not TYPE_NORMAL
    assert tackle["category"] == "physical"
    # The Ruleset owns Excalibur, which the fork lacks -> surfaced as created.
    assert "excalibur" in ids
    excalibur = next(m for m in moves if m["chrooked_id"] == "excalibur")
    assert excalibur["base"] == {}
    assert "type" in excalibur["overridden_fields"]


# --- type-chart slice ac4: per-Target type-chart backdrop; snapshot cached -- #


def test_type_chart_ac4_target_backdrop_and_snapshot_cache(
    client: TestClient, fork: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_id = _register(client, fork)

    # spy on build_snapshot to prove it runs once across two type-chart requests.
    calls = {"n": 0}
    real_build = targetsmod.snapmod.build_snapshot

    def counting_build(base_dir):  # noqa: ANN001
        calls["n"] += 1
        return real_build(base_dir)

    monkeypatch.setattr(targetsmod.snapmod, "build_snapshot", counting_build)

    first = client.get(f"/api/targets/{target_id}/type-chart")
    assert first.status_code == 200, first.text
    second = client.get(f"/api/targets/{target_id}/type-chart")
    assert second.status_code == 200

    assert calls["n"] == 1, "snapshot should be built once and cached"

    cells = first.json()
    # the fork's full 2x2 grid shows through (4 cells), keyed by neutral names.
    assert len(cells) == 4
    by_pair = {(c["attacker"], c["defender"]): c for c in cells}
    # base-only fork cell (Grass->Fire 0.5) is unflagged with null base_multiplier.
    grass_fire = by_pair[("Grass", "Fire")]
    assert grass_fire["overridden"] is False
    assert grass_fire["multiplier"] == 0.5
    assert grass_fire["base_multiplier"] is None
    # the Ruleset override (Fire->Grass 0.5) merges onto the FORK's own cell (2.0),
    # not the committed base — proving the backdrop reads the fork.
    fire_grass = by_pair[("Fire", "Grass")]
    assert fire_grass["overridden"] is True
    assert fire_grass["multiplier"] == 0.5
    assert fire_grass["base_multiplier"] == 2.0


# --- ac8: DATA-ONLY created ability appears with a working packet link ------ #


def test_ac8_data_only_ability_has_working_packet(
    client: TestClient, fork: Path
) -> None:
    target_id = _register(client, fork)
    body = client.post(f"/api/targets/{target_id}/preview").json()

    data_only = body["data_only"]
    assert any(item["chrooked_id"] == "striker" for item in data_only), data_only
    striker = next(item for item in data_only if item["chrooked_id"] == "striker")
    assert striker["packet_url"] == ("/api/behaviors/striker/packet?engine=pokeemerald")

    packet = client.get(striker["packet_url"])
    assert packet.status_code == 200, packet.text
    payload = packet.json()
    assert payload["chrooked_id"] == "striker"
    assert "Striker" in payload["markdown"]
    assert len(payload["markdown"]) > 0


# --- dialect endpoint -------------------------------------------------------- #

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials_dialect"


def _register_essentials(client: TestClient, path: Path) -> str:
    """Register an Essentials target (engine='essentials')."""
    # Essentials targets need to be a git repo for the registry add() validation
    import subprocess

    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t.test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "test"], check=True)
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)

    response = client.post(
        "/api/targets",
        json={"label": "Essentials Fork", "path": str(path), "engine": "essentials"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_dialect_endpoint_modern_v21(client: TestClient, tmp_path: Path) -> None:
    """GET /api/targets/{id}/dialect on a modern v21 PBS returns essentials21."""
    import shutil

    target = tmp_path / "modern_target"
    shutil.copytree(_FIXTURES / "modern_v21", target)
    target_id = _register_essentials(client, target)

    resp = client.get(f"/api/targets/{target_id}/dialect")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dialect"] == "essentials21"
    assert body["label"] == "v19+ (modern)"


def test_dialect_endpoint_english_162(client: TestClient, tmp_path: Path) -> None:
    """GET /api/targets/{id}/dialect on a 16.2-shape PBS returns essentials16."""
    import shutil

    target = tmp_path / "162_target"
    shutil.copytree(_FIXTURES / "english_162", target)
    target_id = _register_essentials(client, target)

    resp = client.get(f"/api/targets/{target_id}/dialect")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dialect"] == "essentials16"
    assert body["label"] == "16.2"


def test_dialect_endpoint_pokeemerald_returns_null(client: TestClient, fork: Path) -> None:
    """GET /api/targets/{id}/dialect on a pokeemerald target returns null dialect."""
    target_id = _register(client, fork)

    resp = client.get(f"/api/targets/{target_id}/dialect")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dialect"] is None
    assert body["label"] is None


def test_dialect_endpoint_unknown_target_returns_404(client: TestClient) -> None:
    """GET /api/targets/nonexistent/dialect returns 404."""
    resp = client.get("/api/targets/doesnotexist/dialect")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# #27 acceptance criteria (Essentials Target apply support)
# ---------------------------------------------------------------------------

_E162_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"
_E162_DIALECT_FIXTURES = Path(__file__).parent / "fixtures" / "essentials_dialect" / "english_162"


def _write_essentials162_fork(target: Path) -> None:
    """A minimal but real Essentials 16.2 fork the applier can apply to.

    Combines the dialect-detection fixtures (PBS/moves.txt, PBS/pokemon.txt) with
    the applier fixtures (abilities.txt, types.txt) so both detection and apply work
    on the same path.
    """
    import shutil

    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    # Dialect-detection files (flat-CSV moves + numeric-section pokemon)
    shutil.copy(_E162_DIALECT_FIXTURES / "PBS" / "moves.txt", pbs / "moves.txt")
    shutil.copy(_E162_DIALECT_FIXTURES / "PBS" / "pokemon.txt", pbs / "pokemon.txt")
    # Applier-required files from the essentials162 fixture set
    shutil.copy(_E162_FIXTURES / "abilities.txt", pbs / "abilities.txt")
    shutil.copy(_E162_FIXTURES / "types.txt", pbs / "types.txt")


def _write_essentials162_ruleset(root: Path) -> None:
    """A minimal Ruleset that exercises the Essentials 16.2 applier.

    Uses Bulbasaur (present in pokemon.txt as BULBASAUR) with a stat override.
    No owned moves/abilities that would trigger creation (keeps the fixture
    simple and the test deterministic).
    """
    (root / "species").mkdir(parents=True)
    (root / "abilities").mkdir(parents=True)
    (root / "moves").mkdir(parents=True)
    (root / "behaviors").mkdir(parents=True)
    (root / "type-chart").mkdir(parents=True)
    (root / "type-chart" / "overrides.yaml").write_text(
        "overrides: []\n", encoding="utf-8"
    )
    (root / "meta.yaml").write_text(
        "base_version: 1.11.2\nschema_version: 1\n", encoding="utf-8"
    )
    (root / "species" / "bulbasaur.yaml").write_text(
        "name: Bulbasaur\n"
        "chrooked_id: bulbasaur\n"
        "aka: { essentials: BULBASAUR }\n"
        "stats: { hp: 55 }\n",
        encoding="utf-8",
    )


@pytest.fixture
def essentials162_ruleset_dir(tmp_path: Path) -> Path:
    root = tmp_path / "ruleset162"
    _write_essentials162_ruleset(root)
    return root


@pytest.fixture
def essentials162_client(
    snapshot_path: Path,
    essentials162_ruleset_dir: Path,
    targets_path: Path,
) -> TestClient:
    app = create_app(
        ruleset_dir=essentials162_ruleset_dir,
        snapshot_path=snapshot_path,
        targets_path=targets_path,
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def essentials162_fork(tmp_path: Path) -> Path:
    """A committed-clean essentials 16.2 git fork the applier can apply to."""
    path = tmp_path / "essentials162_fork"
    _write_essentials162_fork(path)
    _init_committed_repo(path)
    return path


# ac1: registering an Essentials Target works and appears in GET /api/targets
def test_ac1_essentials_target_registers(
    essentials162_client: TestClient, essentials162_fork: Path
) -> None:
    """POST /api/targets engine=essentials → 200; GET /api/targets includes it."""
    add = essentials162_client.post(
        "/api/targets",
        json={
            "label": "Essentials 16.2 Fork",
            "path": str(essentials162_fork),
            "engine": "essentials",
        },
    )
    assert add.status_code == 200, add.text
    body = add.json()
    assert body["engine"] == "essentials"
    target_id = body["id"]

    listed = essentials162_client.get("/api/targets").json()
    assert any(t["id"] == target_id for t in listed)


# ac4: preview on english_162 returns ApplyReportSummary; fork is clean after;
# apply keeps the changes.
def test_ac4_essentials162_preview_clean_and_apply_keeps(
    essentials162_client: TestClient, essentials162_fork: Path
) -> None:
    """Essentials 16.2 preview produces a report and leaves the fork git-clean.

    Then apply keeps the changes (fork is dirty after apply).
    """
    # Register
    add = essentials162_client.post(
        "/api/targets",
        json={
            "label": "Essentials 16.2 Fork",
            "path": str(essentials162_fork),
            "engine": "essentials",
        },
    )
    assert add.status_code == 200, add.text
    target_id = add.json()["id"]

    # Preview
    preview = essentials162_client.post(f"/api/targets/{target_id}/preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    # The ApplyReportSummary keys must be present
    assert {"applied", "partial", "blocked", "created", "data_only"} <= set(body)

    # D1 revert: fork must be git-clean after preview
    porcelain = subprocess.run(
        ["git", "-C", str(essentials162_fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert porcelain == "", f"fork not clean after preview: {porcelain!r}"

    # Apply: changes must be kept
    apply_resp = essentials162_client.post(
        f"/api/targets/{target_id}/apply", json={}
    )
    assert apply_resp.status_code == 200, apply_resp.text
    porcelain_after = subprocess.run(
        ["git", "-C", str(essentials162_fork), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert porcelain_after != "", "apply should leave the fork dirty (changes kept)"


# ---------------------------------------------------------------------------
# dispatch.py unit tests
# ---------------------------------------------------------------------------


def test_dispatch_essentials16_routes_to_essentials162(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """route_apply: engine=essentials + dialect=essentials16 → _apply_essentials162."""
    import chrooked_pokedex.appliers.dispatch as dispatch_mod
    import chrooked_pokedex.cli as cli_mod

    called_as: list[str] = []

    def fake_162(target, category, ruleset, report):  # noqa: ANN001
        called_as.append("essentials162")

    monkeypatch.setattr(cli_mod, "_apply_essentials162", fake_162)

    from chrooked_pokedex.report import ApplyReport

    class _FakeRuleset:
        pass

    report = ApplyReport()
    target = tmp_path
    dispatch_mod.route_apply(
        target, "essentials", _FakeRuleset(), report, dialect="essentials16"
    )
    assert called_as == ["essentials162"], "essentials16 dialect must route to _apply_essentials162"


def test_dispatch_unrecognized_essentials_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """route_apply: essentials + undetectable dialect → blocked entry, no file writes."""
    import chrooked_pokedex.appliers.dispatch as dispatch_mod
    from chrooked_pokedex.report import ApplyReport

    # Force detect_dialect to return None (unrecognized format).
    monkeypatch.setattr(dispatch_mod, "detect_dialect", lambda _target: None)

    class _FakeRuleset:
        pass

    report = ApplyReport()
    dispatch_mod.route_apply(tmp_path, "essentials", _FakeRuleset(), report)

    counts = report.counts()
    assert counts["blocked"] == 1, "must record one blocked entry"
    assert counts["applied"] == 0, "must not apply anything"
    # No files should have been written to tmp_path
    written = list(tmp_path.rglob("*"))
    assert written == [], f"must write nothing on unrecognized format, got: {written}"
