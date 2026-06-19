"""Optional `.env` loading so users can keep provider keys + config in one file.

The frictionless "bring your own key" pattern for the provider-agnostic LLM
client (#6): drop `LLM_PROVIDER` / `LLM_MODEL` / `ANTHROPIC_API_KEY` (etc.) in a
repo-root `.env` instead of exporting them on every launch.

Two invariants:
- **A real environment variable always wins** (`override=False`), so `.env` is a
  default, never a clobber.
- **Missing `python-dotenv` is a silent no-op**, so the app still runs without it
  (the dependency is declared, but resilience over a hard crash).
"""

from __future__ import annotations

import os
from pathlib import Path

# This file is src/chrooked_pokedex/env.py → repo root is two parents up from the
# package dir (env.py → chrooked_pokedex → src → repo).
_REPO_ROOT = Path(__file__).resolve().parents[2]


def load_env_file(path: Path | None = None) -> bool:
    """Load `<repo>/.env` into `os.environ` if present; a real env var wins.

    Returns ``True`` when a file was loaded, ``False`` when python-dotenv is not
    installed or no `.env` exists. Never overrides an already-set variable, and
    never logs values.
    """
    # Escape hatch for hermetic tests (and containers that inject env directly):
    # CHROOKED_SKIP_DOTENV disables the default repo-root auto-load so a developer's
    # real `.env` never bleeds into a test. An EXPLICIT `path` is always honored.
    if path is None and os.environ.get("CHROOKED_SKIP_DOTENV"):
        return False

    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    env_path = path or (_REPO_ROOT / ".env")
    if not env_path.is_file():
        return False

    # override=False → the real environment takes precedence over the file.
    return bool(load_dotenv(dotenv_path=os.fspath(env_path), override=False))
