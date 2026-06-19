"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _hermetic_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the suite independent of any developer's real repo-root ``.env``.

    `create_app` / `create_app_from_env` auto-load `.env` so the server picks up
    provider keys; in tests that would let a local `.env` defeat env-dependent
    assertions (e.g. the missing-key path). Setting ``CHROOKED_SKIP_DOTENV``
    disables only the default auto-load — `test_env.py`, which calls
    ``load_env_file`` with an explicit path, is unaffected.
    """
    monkeypatch.setenv("CHROOKED_SKIP_DOTENV", "1")
