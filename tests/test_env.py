"""`.env` loading (#36): values land in the environment, and a real env var wins."""

from __future__ import annotations

import os

from chrooked_pokedex.env import load_env_file


def test_env_file_value_loads(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CHROOKED_TEST_KEY=from_dotenv\n", encoding="utf-8")
    monkeypatch.delenv("CHROOKED_TEST_KEY", raising=False)

    loaded = load_env_file(env)

    assert loaded is True
    assert os.environ["CHROOKED_TEST_KEY"] == "from_dotenv"


def test_real_env_var_is_not_overridden(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CHROOKED_TEST_KEY=from_dotenv\n", encoding="utf-8")
    monkeypatch.setenv("CHROOKED_TEST_KEY", "from_real_env")

    load_env_file(env)

    # A value already in the real environment always wins over the file.
    assert os.environ["CHROOKED_TEST_KEY"] == "from_real_env"


def test_missing_file_is_a_noop(tmp_path):
    assert load_env_file(tmp_path / "nope.env") is False
