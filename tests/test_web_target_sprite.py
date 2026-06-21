"""Unit tests for GET /api/targets/{target_id}/sprite/{dex}.

AAA-shaped, hermetic (unit marker): builds a tmp Essentials target directory
with a real PNG file, registers it, and asserts the route returns 200 +
image/png for a present dex number and 404 for a missing one.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web.app import create_app

# Minimal valid PNG (1×1 transparent pixel).
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

_MINIMAL_SNAPSHOT: dict = {
    "version": "1.11.2",
    "species": {},
    "moves": {},
    "abilities": {},
    "type_chart": [],
}

_MINIMAL_RULESET_YAML = """\
kind: meta
version: "0.1"
"""


def _write_minimal_ruleset(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "meta.yaml").write_text(_MINIMAL_RULESET_YAML, encoding="utf-8")


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t.test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "test"], check=True)
    (path / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)


@pytest.mark.unit
def test_sprite_endpoint_returns_png_and_404(tmp_path: Path) -> None:
    """Arrange: an Essentials target with Graphics/Battlers/Front/001.png.
    Act:   GET /api/targets/{id}/sprite/1 and GET …/sprite/999.
    Assert: dex=1 → 200 + image/png; dex=999 → 404.
    """
    # --- Arrange ---
    target_dir = tmp_path / "ess_target"
    front_dir = target_dir / "Graphics" / "Battlers" / "Front"
    front_dir.mkdir(parents=True)
    (front_dir / "001.png").write_bytes(_TINY_PNG)
    _init_git_repo(target_dir)

    ruleset_dir = tmp_path / "ruleset"
    _write_minimal_ruleset(ruleset_dir)

    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(_MINIMAL_SNAPSHOT), encoding="utf-8")

    targets_path = tmp_path / "targets.json"

    app = create_app(
        ruleset_dir=ruleset_dir,
        snapshot_path=snapshot_path,
        targets_path=targets_path,
    )
    client = TestClient(app, raise_server_exceptions=False)

    reg_resp = client.post(
        "/api/targets",
        json={"label": "Ess Fork", "path": str(target_dir), "engine": "essentials"},
    )
    assert reg_resp.status_code == 200, reg_resp.text
    target_id = reg_resp.json()["id"]

    # --- Act + Assert: present sprite ---
    hit = client.get(f"/api/targets/{target_id}/sprite/1")
    assert hit.status_code == 200, hit.text
    assert hit.headers["content-type"] == "image/png"

    # --- Act + Assert: missing sprite ---
    miss = client.get(f"/api/targets/{target_id}/sprite/999")
    assert miss.status_code == 404, miss.text
