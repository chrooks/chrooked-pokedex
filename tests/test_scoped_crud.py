"""Scoped CRUD: an edit lands in base or a Target Override namespace."""

from pathlib import Path

import pytest

from chrooked_pokedex.web import crud


def _base_kricketune(ruleset_dir: Path) -> Path:
    species = ruleset_dir / "species"
    species.mkdir(parents=True)
    path = species / "kricketune.yaml"
    crud.upsert_species(
        ruleset_dir,
        "kricketune",
        {"name": "Kricketune", "chrooked_id": "kricketune", "types": ["Bug", "Normal"]},
    )
    return path


@pytest.mark.unit
def test_resolve_scope_dir_base_is_ruleset_dir(tmp_path: Path) -> None:
    assert crud.resolve_scope_dir(tmp_path, "base") == tmp_path
    assert crud.resolve_scope_dir(tmp_path, None) == tmp_path


@pytest.mark.unit
def test_resolve_scope_dir_target_creates_namespace_meta(tmp_path: Path) -> None:
    scoped = crud.resolve_scope_dir(tmp_path, "target:africanvs", engine="essentials", label="Chrooked Africanvs")

    assert scoped == tmp_path / "targets" / "africanvs"
    meta = (scoped / "meta.yaml").read_text(encoding="utf-8")
    assert "slug: africanvs" in meta
    assert "engine: essentials" in meta


@pytest.mark.unit
def test_resolve_scope_dir_rejects_bad_scope(tmp_path: Path) -> None:
    with pytest.raises(crud.ValidationError):
        crud.resolve_scope_dir(tmp_path, "garbage")
    with pytest.raises(crud.ValidationError):
        crud.resolve_scope_dir(tmp_path, "target:Bad Slug")


@pytest.mark.unit
def test_scoped_write_lands_in_namespace_base_untouched(tmp_path: Path) -> None:
    base_path = _base_kricketune(tmp_path)
    base_before = base_path.read_text(encoding="utf-8")

    scope_dir = crud.resolve_scope_dir(tmp_path, "target:africanvs", engine="essentials", label="Africanvs")
    crud.upsert_species(
        scope_dir,
        "kricketune",
        {"name": "Kricketune", "chrooked_id": "kricketune", "types": ["Bug", "Fighting"]},
    )

    target_path = tmp_path / "targets" / "africanvs" / "species" / "kricketune.yaml"
    assert target_path.exists()
    assert "Fighting" in target_path.read_text(encoding="utf-8")
    # base file is byte-unchanged
    assert base_path.read_text(encoding="utf-8") == base_before
    assert "Fighting" not in base_before
