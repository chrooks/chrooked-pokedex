"""Design pipeline routes: propose — registered onto the /api/design router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def register(router: APIRouter, ctx: Any) -> None:
    """Filled by M2."""
