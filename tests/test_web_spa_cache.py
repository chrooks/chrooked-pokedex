"""The SPA bundle's caching contract.

A content-hashed asset may be cached forever; the HTML that names those hashes
may not. Without that split a browser can sit on a stale ``index.html``, keep
requesting the asset hashes it names, and run an old build indefinitely — which
happened on the handheld this app is used from, and presents as "the fix did
nothing" rather than as a caching problem.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web.app import create_app

pytestmark = pytest.mark.unit


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A minimal built-frontend directory: an index plus one hashed asset."""
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(
        '<!doctype html><html><head>'
        '<link rel="stylesheet" href="/assets/index-abc123.css">'
        '</head><body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (root / "assets" / "index-abc123.css").write_text(":root{color:red}", encoding="utf-8")
    return root


@pytest.fixture
def client(dist: Path, tmp_path: Path) -> TestClient:
    """The app with the SPA mounted. The Ruleset content is irrelevant here —
    these tests are about how static files are served — so it is the smallest
    tree that loads."""
    ruleset = tmp_path / "ruleset"
    for kind in ("species", "moves", "abilities", "behaviors", "type-chart"):
        (ruleset / kind).mkdir(parents=True)
    (ruleset / "meta.yaml").write_text("base_version: 1.11.2\n", encoding="utf-8")
    snapshot = tmp_path / "1.11.2.json"
    snapshot.write_text(json.dumps({"version": "1.11.2", "species": {}}), encoding="utf-8")

    app = create_app(
        ruleset_dir=ruleset,
        snapshot_path=snapshot,
        targets_path=tmp_path / "targets.json",
        dist_dir=dist,
    )
    return TestClient(app)


def test_index_html_must_be_revalidated(client: TestClient) -> None:
    """The document naming the asset hashes may never be served from cache blind."""
    response = client.get("/")
    assert response.status_code == 200
    cache_control = response.headers.get("cache-control", "")
    assert "no-cache" in cache_control, (
        "index.html without no-cache falls under heuristic freshness: the browser "
        "may reuse it without revalidating and keep loading an old bundle"
    )


def test_hashed_assets_are_not_forced_to_revalidate(client: TestClient) -> None:
    """Fingerprinted files are immutable by construction; leave them cacheable."""
    response = client.get("/assets/index-abc123.css")
    assert response.status_code == 200
    assert "no-cache" not in response.headers.get("cache-control", "")


def test_unknown_paths_404_rather_than_falling_back_to_the_shell(client: TestClient) -> None:
    """There is deliberately no SPA deep-link fallback.

    Every view in this app is addressed by query string (`/?kind=moves`), never
    by path, so a request for a real path that does not exist is a genuine 404
    and should say so. A catch-all rewrite to index.html would turn typos and
    missing assets into a blank app screen instead.
    """
    assert client.get("/some/client/route").status_code == 404


def test_the_api_is_unaffected_by_the_static_mount(client: TestClient) -> None:
    """Mounting the SPA at / must not shadow or re-header the API."""
    response = client.get("/api/targets")
    assert response.status_code == 200
    assert isinstance(json.loads(response.text), list)
