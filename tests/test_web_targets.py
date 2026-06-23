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


# ---------------------------------------------------------------------------
# #27 ac4 — NON-GIT Essentials target: snapshot-restore preview safety
# ---------------------------------------------------------------------------


@pytest.fixture
def essentials162_nongit_fork(tmp_path: Path) -> Path:
    """A plain directory (NOT a git repo) containing a minimal Essentials 16.2 PBS set.

    This mirrors the real Africanvs source layout: an Essentials game folder that
    was never git-init'd.  The fixture is a copy of english_162 so dialect detection
    returns 'essentials16' and the applier can run.
    """
    path = tmp_path / "essentials162_plain"
    _write_essentials162_fork(path)
    # Explicitly verify no .git present — this is the invariant the test is built on.
    assert not (path / ".git").exists(), "fixture must NOT be a git repo"
    return path


def test_ac1_add_accepts_non_git_essentials_dir(
    essentials162_client: TestClient, essentials162_nongit_fork: Path
) -> None:
    """POST /api/targets with engine=essentials and a plain (non-git) dir → 200.

    After the fix, the registry must allow non-git Essentials directories.
    """
    response = essentials162_client.post(
        "/api/targets",
        json={
            "label": "Non-git Essentials",
            "path": str(essentials162_nongit_fork),
            "engine": "essentials",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine"] == "essentials"
    assert Path(body["path"]) == essentials162_nongit_fork.resolve()


def test_ac4_nongit_essentials_preview_snapshot_restores_and_apply_keeps(
    essentials162_client: TestClient, essentials162_nongit_fork: Path
) -> None:
    """Preview on a NON-GIT Essentials target: snapshot-restore leaves files byte-identical.

    Then apply keeps the changes.

    Proof:
    (a) POST .../preview → ApplyReportSummary keys present.
    (b) After preview, PBS/*.txt files are byte-identical to before (snapshot-restore worked).
    (c) POST .../apply → report returned, PBS files differ from pre-preview state.
    """
    import hashlib

    pbs_dir = essentials162_nongit_fork / "PBS"

    def _hashes() -> dict[str, str]:
        """SHA-256 fingerprint of every *.txt in PBS/."""
        result = {}
        for f in sorted(pbs_dir.glob("*.txt")):
            result[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        return result

    # Snapshot hashes BEFORE preview.
    before_hashes = _hashes()
    assert before_hashes, "fixture must have PBS/*.txt files"

    # Register the non-git target.
    add = essentials162_client.post(
        "/api/targets",
        json={
            "label": "Non-git Essentials",
            "path": str(essentials162_nongit_fork),
            "engine": "essentials",
        },
    )
    assert add.status_code == 200, add.text
    target_id = add.json()["id"]

    # (a) Preview returns an ApplyReportSummary.
    preview = essentials162_client.post(f"/api/targets/{target_id}/preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert {"applied", "partial", "blocked", "created", "data_only"} <= set(body)

    # (b) PBS files are byte-identical after preview (snapshot-restore worked).
    after_preview_hashes = _hashes()
    assert after_preview_hashes == before_hashes, (
        "Preview must leave PBS files byte-identical via snapshot-restore. "
        f"Changed: {set(after_preview_hashes) ^ set(before_hashes)}"
    )

    # (c) Apply keeps changes: PBS files must differ from before.
    apply_resp = essentials162_client.post(f"/api/targets/{target_id}/apply", json={})
    assert apply_resp.status_code == 200, apply_resp.text
    after_apply_hashes = _hashes()
    # At least one PBS file must have been modified by the applier.
    assert after_apply_hashes != before_hashes, (
        "Apply must write changes to PBS files and keep them."
    )


# ---------------------------------------------------------------------------
# #41 — Essentials English-name relabeling (ac1–ac4)
# ---------------------------------------------------------------------------
#
# These tests prove that Essentials target backdrop functions replace localized
# (e.g. Spanish) PBS display names with canonical English names from the base
# snapshot ⊕ Ruleset, falling back to a prettified InternalName when a move/
# ability/species has no canonical English entry.
# ---------------------------------------------------------------------------

_SPANISH_162 = Path(__file__).parent / "fixtures" / "essentials_dialect" / "spanish_162"


def _make_english_base_snapshot() -> dict:
    """A minimal base snapshot with English names for EARTHQUAKE, STENCH, BULBASAUR."""
    return {
        "version": "1.11.2",
        "species": {
            "bulbasaur": {
                "dex": 1,
                "chrooked_id": "bulbasaur",
                "name": "Bulbasaur",
                "types": ["Grass", "Poison"],
                "abilities": {"primary": "Overgrow", "secondary": None, "hidden": "Chlorophyll"},
                "stats": {"hp": 45, "atk": 49, "def": 49, "spe": 45, "spa": 65, "spd": 65},
                "learnset": [],
            },
        },
        "moves": {
            "megahorn": {
                "chrooked_id": "megahorn",
                "name": "Megahorn",
                "aka": {},
                "type": "Bug",
                "category": "physical",
                "power": 120,
                "accuracy": 85,
                "pp": 10,
                "description": "Using its tough and impressive horn, the user rams into the target with no letup.",
            },
            "tackle": {
                "chrooked_id": "tackle",
                "name": "Tackle",
                "aka": {},
                "type": "Normal",
                "category": "physical",
                "power": 40,
                "accuracy": 100,
                "pp": 35,
                "description": "A physical attack in which the user charges, tacks, or butts the target.",
            },
            "growl": {
                "chrooked_id": "growl",
                "name": "Growl",
                "aka": {},
                "type": "Normal",
                "category": "status",
                "power": None,
                "accuracy": 100,
                "pp": 40,
                "description": "The user growls in an endearing way, making opposing Pokemon less wary.",
            },
            "earthquake": {
                "chrooked_id": "earthquake",
                "name": "Earthquake",
                "aka": {},
                "type": "Ground",
                "category": "physical",
                "power": 100,
                "accuracy": 100,
                "pp": 10,
                "description": "The user sets off an earthquake that strikes every Pokemon around it.",
            },
        },
        "abilities": {
            "stench": {
                "chrooked_id": "stench",
                "name": "Stench",
                "description": "The stench may cause the target to flinch.",
                "aka": {},
            },
            "overgrow": {
                "chrooked_id": "overgrow",
                "name": "Overgrow",
                "description": "Powers up Grass-type moves in a pinch.",
                "aka": {},
            },
        },
        "type_chart": [],
    }


def _make_english_ruleset_with_excalibur(tmp_path: Path) -> Path:
    """A Ruleset that owns one chrooked ORIGINAL move: Excalibur."""
    root = tmp_path / "ruleset_excalibur"
    (root / "species").mkdir(parents=True)
    (root / "abilities").mkdir(parents=True)
    (root / "moves").mkdir(parents=True)
    (root / "behaviors").mkdir(parents=True)
    (root / "type-chart").mkdir(parents=True)
    (root / "type-chart" / "overrides.yaml").write_text("overrides: []\n", encoding="utf-8")
    (root / "meta.yaml").write_text(
        "base_version: 1.11.2\nschema_version: 1\n", encoding="utf-8"
    )
    (root / "moves" / "excalibur.yaml").write_text(
        "name: Excalibur\n"
        "chrooked_id: excalibur\n"
        "aka: { essentials: EXCALIBUR }\n"
        "type: Steel\n"
        "category: physical\n"
        "power: 90\n"
        "accuracy: 100\n"
        "pp: 10\n"
        "description: A holy sword strike.\n",
        encoding="utf-8",
    )
    return root


def _essentials_target_41(path: Path) -> "targetsmod.Target":
    from chrooked_pokedex.web.targets import Target
    return Target(id="esp1", label="Spanish 16.2", path=str(path), engine="essentials")


# ac1: EARTHQUAKE shows English; STENCH shows English; species English name.
def test_ac1_spanish_162_backdrop_shows_english_names(tmp_path: Path) -> None:
    """target_moves/target_abilities/target_dex for a Spanish Essentials target show English names."""
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web.targets import TargetState, target_abilities, target_dex, target_moves

    base_snapshot = _make_english_base_snapshot()
    ruleset_dir = _make_english_ruleset_with_excalibur(tmp_path)
    ruleset = Ruleset.load(ruleset_dir)
    target = _essentials_target_41(_SPANISH_162)
    state = TargetState()

    moves = target_moves(target, ruleset, state, base_snapshot=base_snapshot)
    abilities = target_abilities(target, ruleset, state, base_snapshot=base_snapshot)
    dex = target_dex(target, ruleset, state, base_snapshot=base_snapshot)

    move_by_id = {m["chrooked_id"]: m for m in moves}
    # EARTHQUAKE: Spanish PBS name is "Terremoto"; English canonical is "Earthquake".
    assert move_by_id["earthquake"]["name"] == "Earthquake", (
        f"Expected 'Earthquake', got {move_by_id['earthquake']['name']!r}"
    )
    # MEGAHORN is also in base → English "Megahorn".
    assert move_by_id["megahorn"]["name"] == "Megahorn"

    ability_by_id = {a["chrooked_id"]: a for a in abilities}
    # STENCH: Spanish PBS name is "Hedor"; English canonical is "Stench".
    assert ability_by_id["stench"]["name"] == "Stench", (
        f"Expected 'Stench', got {ability_by_id['stench']['name']!r}"
    )

    dex_by_id = {e["chrooked_id"]: e for e in dex}
    # BULBASAUR: English name in base.
    assert dex_by_id["bulbasaur"]["name"] == "Bulbasaur"


# ac2: chrooked-owned EXCALIBUR (in Ruleset) shows English chrooked name.
def test_ac2_chrooked_original_shows_english_ruleset_name(tmp_path: Path) -> None:
    """A move present ONLY in the Ruleset (Excalibur) shows its English chrooked name."""
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web.targets import TargetState, target_moves

    # Add EXCALIBUR to the spanish_162 PBS so the target snapshot sees it.
    pbs = _SPANISH_162 / "PBS" / "moves.txt"
    original_text = pbs.read_text(encoding="utf-8")
    excalibur_row = "6,EXCALIBUR,Excalibur Español,000,90,STEEL,Physical,100,10,0,00,0,abef,\"Golpe espada sagrada.\"\n"
    pbs_with_excalibur = tmp_path / "excalibur_pbs"
    import shutil
    shutil.copytree(_SPANISH_162, pbs_with_excalibur)
    (pbs_with_excalibur / "PBS" / "moves.txt").write_text(
        original_text + excalibur_row, encoding="utf-8"
    )

    base_snapshot = _make_english_base_snapshot()  # base does NOT have excalibur
    ruleset_dir = _make_english_ruleset_with_excalibur(tmp_path)
    ruleset = Ruleset.load(ruleset_dir)
    target = _essentials_target_41(pbs_with_excalibur)
    state = TargetState()

    moves = target_moves(target, ruleset, state, base_snapshot=base_snapshot)
    excalibur = next((m for m in moves if m["chrooked_id"] == "excalibur"), None)
    assert excalibur is not None, "Excalibur not in target_moves output"
    # The Ruleset gives the English name "Excalibur", NOT the Spanish PBS name.
    assert excalibur["name"] == "Excalibur", (
        f"Expected English 'Excalibur', got {excalibur['name']!r}"
    )


# ac3: target-only AFRICANVSORIGINAL falls back to prettified InternalName.
def test_ac3_target_only_move_prettifies_internal_name(tmp_path: Path) -> None:
    """A move unknown to base ⊕ Ruleset falls back to a prettified InternalName label."""
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web.targets import TargetState, target_moves

    base_snapshot = _make_english_base_snapshot()  # no AFRICANVSORIGINAL
    ruleset_dir = _make_english_ruleset_with_excalibur(tmp_path)
    ruleset = Ruleset.load(ruleset_dir)
    target = _essentials_target_41(_SPANISH_162)
    state = TargetState()

    moves = target_moves(target, ruleset, state, base_snapshot=base_snapshot)
    original = next((m for m in moves if m["chrooked_id"] == "africanvsoriginal"), None)
    assert original is not None, "AFRICANVSORIGINAL not in target_moves output"
    # Must NOT be the Spanish PBS display name.
    assert original["name"] != "Golpe Especial Africano", (
        "Should not show the Spanish PBS name; should prettify the InternalName."
    )
    # Must look like a prettified InternalName (title-cased, no Spanish).
    name = original["name"]
    assert name[0].isupper(), f"Prettified name should start uppercase, got {name!r}"
    assert name == name.title() or name.replace(" ", "").isalpha(), (
        f"Prettified name should be title-cased English, got {name!r}"
    )


# ac4: VALUES unchanged after relabel; pokeemerald target names unchanged.
def test_ac4_values_unchanged_and_pokeemerald_unaffected(tmp_path: Path) -> None:
    """Relabeling only changes 'name'; all other fields stay at target's PBS values.

    Also proves pokeemerald target_moves is not affected (no relabeling).
    """
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web.targets import Target, TargetState, target_moves

    base_snapshot = _make_english_base_snapshot()
    ruleset_dir = _make_english_ruleset_with_excalibur(tmp_path)
    ruleset = Ruleset.load(ruleset_dir)
    target = _essentials_target_41(_SPANISH_162)
    state_es = TargetState()

    # EARTHQUAKE in the Spanish PBS has power=100, accuracy=100, pp=10, type=Ground.
    moves = target_moves(target, ruleset, state_es, base_snapshot=base_snapshot)
    eq = next((m for m in moves if m["chrooked_id"] == "earthquake"), None)
    assert eq is not None
    assert eq["name"] == "Earthquake", "name must be English"
    assert eq["power"] == 100, "power must come from the Spanish PBS (target's own value)"
    assert eq["accuracy"] == 100
    assert eq["pp"] == 10
    assert eq["type"] == "Ground"

    # pokeemerald target: target_moves without base_snapshot → no relabeling.
    poke_target = Target(id="poke1", label="Poke", path="/tmp/irrelevant", engine="pokeemerald")
    state_poke = TargetState()
    # monkeypatch snapshot_for to return a minimal snapshot directly
    # (we don't have a real pokeemerald tree here, just prove no relabeling happens).
    from unittest.mock import patch

    minimal_snap = {
        "version": "1.11.2",
        "species": {},
        "moves": {
            "tackle": {
                "chrooked_id": "tackle",
                "name": "Tackle",
                "aka": {},
                "type": "Normal",
                "category": "physical",
                "power": 40,
                "accuracy": 100,
                "pp": 35,
                "description": "",
            }
        },
        "abilities": {},
        "type_chart": [],
    }
    with patch.object(state_poke, "snapshot_for", return_value=minimal_snap):
        poke_moves = target_moves(
            poke_target, ruleset, state_poke, base_snapshot=base_snapshot
        )
    tackle = next((m for m in poke_moves if m["chrooked_id"] == "tackle"), None)
    assert tackle is not None
    # For pokeemerald, name stays as-is from the snapshot (no relabeling).
    assert tackle["name"] == "Tackle"


# --- #39: nested species learnset moves render canonical English ------------ #
def test_issue39_spanish_learnset_moves_render_english(tmp_path: Path) -> None:
    """target_dex relabels each species' learnset[].move to canonical English."""
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web.targets import TargetState, target_dex

    base_snapshot = _make_english_base_snapshot()
    ruleset_dir = _make_english_ruleset_with_excalibur(tmp_path)
    ruleset = Ruleset.load(ruleset_dir)
    target = _essentials_target_41(_SPANISH_162)
    state = TargetState()

    dex = target_dex(target, ruleset, state, base_snapshot=base_snapshot)
    dex_by_id = {e["chrooked_id"]: e for e in dex}
    learnset = dex_by_id["bulbasaur"]["learnset"]
    # The Spanish PBS Moves line is 1,TACKLE,1,GROWL — base gives English names.
    assert learnset == [
        {"level": 1, "move": "Tackle", "move_id": "tackle"},
        {"level": 1, "move": "Growl", "move_id": "growl"},
    ]


def test_issue39_ruleset_learnset_override_keeps_english_names(tmp_path: Path) -> None:
    """A Ruleset learnset override (no move_id) must keep its English names, not blank them.

    Regression: build_dex rebuilds an overridden learnset as {level, move} with no
    move_id, so the English relabel used to map the missing move_id to an empty
    string. The override's move names are already English and must survive — and a
    level-0 entry (a valid Ruleset shape) must be preserved.
    """
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web.targets import TargetState, target_dex

    base_snapshot = _make_english_base_snapshot()
    ruleset_dir = _make_english_ruleset_with_excalibur(tmp_path)
    # Add a Bulbasaur learnset override with English display names and a level-0 move.
    (ruleset_dir / "species" / "bulbasaur.yaml").write_text(
        "name: Bulbasaur\n"
        "chrooked_id: bulbasaur\n"
        "learnset:\n"
        "  - { level: 1, move: Cinder Smash }\n"
        "  - { level: 0, move: Air Slash }\n"
        "  - { level: 1, move: Growl }\n",
        encoding="utf-8",
    )
    ruleset = Ruleset.load(ruleset_dir)
    target = _essentials_target_41(_SPANISH_162)
    state = TargetState()

    dex = target_dex(target, ruleset, state, base_snapshot=base_snapshot)
    dex_by_id = {e["chrooked_id"]: e for e in dex}
    learnset = dex_by_id["bulbasaur"]["learnset"]

    # No move blanked to "" by the relabel; the override's English names survive.
    assert all(slot["move"] for slot in learnset), learnset
    assert [(s["level"], s["move"]) for s in learnset] == [
        (1, "Cinder Smash"),
        (0, "Air Slash"),
        (1, "Growl"),
    ]


# --- #43: nested species ability slots render canonical English ------------- #
def test_issue43_spanish_species_ability_slots_render_english(tmp_path: Path) -> None:
    """target_dex relabels nested ability slots; unknown tokens prettify."""
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web.targets import TargetState, target_dex

    base_snapshot = _make_english_base_snapshot()
    ruleset_dir = _make_english_ruleset_with_excalibur(tmp_path)
    ruleset = Ruleset.load(ruleset_dir)
    target = _essentials_target_41(_SPANISH_162)
    state = TargetState()

    dex = target_dex(target, ruleset, state, base_snapshot=base_snapshot)
    dex_by_id = {e["chrooked_id"]: e for e in dex}
    slots = dex_by_id["bulbasaur"]["abilities"]
    # OVERGROW is in the base → canonical English "Overgrow".
    assert slots["primary"] == "Overgrow", f"got {slots['primary']!r}"
    # An empty slot stays None.
    assert slots["secondary"] is None
    # CHLOROPHYLL is NOT in the base → prettified InternalName, never all-caps.
    assert slots["hidden"] == "Chlorophyll", f"got {slots['hidden']!r}"


# --- #44: ability/move descriptions render canonical English ---------------- #
def test_issue44_known_base_description_overlaid_custom_keeps_own(tmp_path: Path) -> None:
    """A known base ability gets the English description; a custom ability keeps its own."""
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web.targets import TargetState, target_abilities

    # Add a target-only ability (no base, no Ruleset entry) to a PBS copy.
    import shutil

    pbs_copy = tmp_path / "desc_pbs"
    shutil.copytree(_SPANISH_162, pbs_copy)
    abilities_txt = pbs_copy / "PBS" / "abilities.txt"
    custom_row = '3,AFRICANVSCUSTOM,Habilidad Custom,"Descripción propia del fork."\n'
    abilities_txt.write_text(
        abilities_txt.read_text(encoding="utf-8") + custom_row, encoding="utf-8"
    )

    base_snapshot = _make_english_base_snapshot()
    ruleset_dir = _make_english_ruleset_with_excalibur(tmp_path)
    ruleset = Ruleset.load(ruleset_dir)
    target = _essentials_target_41(pbs_copy)
    state = TargetState()

    abilities = target_abilities(target, ruleset, state, base_snapshot=base_snapshot)
    by_id = {a["chrooked_id"]: a for a in abilities}

    # STENCH is in the base → English description overlaid over the Spanish one.
    assert by_id["stench"]["description"] == (
        "The stench may cause the target to flinch."
    ), f"got {by_id['stench']['description']!r}"

    # AFRICANVSCUSTOM is NOT in base ⊕ Ruleset → keeps its own (Spanish) description.
    custom = by_id.get("africanvscustom")
    assert custom is not None, "custom ability missing from target_abilities"
    assert custom["description"] == "Descripción propia del fork.", (
        "custom ability must keep its own description, never blank/overlaid"
    )


@pytest.mark.unit
def test_relabel_names_keeps_fakemon_pbs_name() -> None:
    """A target-only fakemon keeps its PBS Name, not a prettified InternalName.

    Regression: the relabel fallback used to prettify the chrooked_id/InternalName
    (`aquilatus` -> "Aquilatus"), clobbering the author's real `Name=Harregg`.
    Canon species still relabel to English; a nameless entry still prettifies.
    """
    from chrooked_pokedex.web.targets import _relabel_names

    english_map = {"pikachu": "Pikachu"}
    entries = [
        {"chrooked_id": "pikachu", "name": "Pikachu (es)"},  # canon -> English
        {"chrooked_id": "aquilatus", "name": "Harregg"},      # fakemon -> keep PBS
        {"chrooked_id": "intuitus", "name": ""},               # no name -> prettify
    ]

    by_id = {e["chrooked_id"]: e["name"] for e in _relabel_names(entries, english_map)}

    assert by_id["pikachu"] == "Pikachu"
    assert by_id["aquilatus"] == "Harregg"
    assert by_id["intuitus"] == "Intuitus"


# --- M3: Target Override layer flows through the backdrop dex + apply -------- #


def test_target_override_backdrop_reflects_overlay_canon_unaffected(
    client: TestClient, fork: Path
) -> None:
    """A scoped edit shows on this target's backdrop but never on the Canon dex."""
    target_id = _register(client, fork)

    # Bind the target to a committed override namespace.
    bind = client.put(f"/api/targets/{target_id}/namespace", json={"slug": "africanvs"})
    assert bind.status_code == 200, bind.text
    assert bind.json()["namespace"] == "africanvs"

    # Scoped edit: Aegislash becomes mono-Ghost with hp 200, Africanvs only.
    put = client.put(
        "/api/species/aegislash?scope=target:africanvs",
        json={
            "name": "Aegislash",
            "chrooked_id": "aegislash",
            "types": ["Ghost"],
            "stats": {"hp": 200},
        },
    )
    assert put.status_code == 200, put.text

    # Backdrop dex reflects the overlay and badges the scoped fields.
    dex = client.get(f"/api/targets/{target_id}/dex")
    assert dex.status_code == 200, dex.text
    entry = next(e for e in dex.json() if e["chrooked_id"] == "aegislash")
    assert entry["types"] == ["Ghost"]
    assert entry["stats"]["hp"] == 200  # overlay wins over base ruleset 140
    assert set(entry["target_overridden_fields"]) == {"types", "stats"}

    # Canon dex is untouched by the namespace edit.
    canon = client.get("/api/dex")
    assert canon.status_code == 200, canon.text
    canon_entry = next(e for e in canon.json() if e["chrooked_id"] == "aegislash")
    assert canon_entry["stats"]["hp"] == 140  # base ruleset, not 200
    assert canon_entry["types"] != ["Ghost"]
    assert "target_overridden_fields" not in canon_entry


def test_target_without_namespace_has_no_badge_fields(
    client: TestClient, fork: Path
) -> None:
    """An unbound target behaves exactly as before — no overlay, no badge."""
    target_id = _register(client, fork)
    dex = client.get(f"/api/targets/{target_id}/dex")
    assert dex.status_code == 200, dex.text
    entry = next(e for e in dex.json() if e["chrooked_id"] == "aegislash")
    assert "target_overridden_fields" not in entry


# --- M4: the Change Ledger records scoped edits and applies ------------------ #


def test_ledger_records_scoped_edit_and_apply(
    client: TestClient, fork: Path, ruleset_dir: Path
) -> None:
    target_id = _register(client, fork)
    client.put(f"/api/targets/{target_id}/namespace", json={"slug": "africanvs"})

    edit = client.put(
        "/api/species/aegislash?scope=target:africanvs",
        json={"name": "Aegislash", "chrooked_id": "aegislash", "types": ["Ghost"]},
    )
    assert edit.status_code == 200, edit.text

    led = client.get("/api/ledger").json()["entries"]
    web_edits = [e for e in led if e["source"] == "web-edit"]
    assert len(web_edits) == 1
    entry = web_edits[0]
    assert entry["scope"] == "target:africanvs"
    assert entry["kind"] == "species"
    assert entry["chrooked_id"] == "aegislash"
    assert "types" in entry["fields"]
    assert entry["fields"]["types"]["to"] == ["Ghost"]

    # An apply against a clean fork records an event entry.
    applied = client.post(f"/api/targets/{target_id}/apply")
    assert applied.status_code == 200, applied.text
    apply_entries = client.get("/api/ledger?kind=apply").json()["entries"]
    assert len(apply_entries) == 1
    assert apply_entries[0]["source"] == "apply"
    assert apply_entries[0]["scope"] == "target:africanvs"
    assert "report" in apply_entries[0]

    # Ledger lives at the BASE ruleset dir, not inside the namespace.
    assert (ruleset_dir / "ledger.ndjson").exists()
    assert not (ruleset_dir / "targets" / "africanvs" / "ledger.ndjson").exists()
