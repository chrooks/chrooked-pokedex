"""Queue row grammar (#103 M1) — parse + resolve against the real base snapshot.

Pure functions over `tests/fixtures/design/queue_sample.md` (Chris's real rows
plus edge cases) and the committed `ruleset/.base/1.11.2.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chrooked_pokedex.web import design_queue as q

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "design" / "queue_sample.md"
_SNAPSHOT = _REPO_ROOT / "ruleset" / ".base" / "1.11.2.json"

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def snapshot() -> dict:
    return json.loads(_SNAPSHOT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def names(snapshot: dict) -> dict[str, str]:
    return q.display_names(snapshot)


@pytest.fixture(scope="module")
def rows(names: dict[str, str]) -> dict[str, q.ParsedRow]:
    parsed = q.parse_rows(_FIXTURE.read_text(encoding="utf-8"), names)
    return {r.raw: r for r in parsed}


def _resolve(raw: str, rows, snapshot, names):
    return q.resolve_row(rows[raw], snapshot, names)


def test_blank_and_comment_rows_are_skipped(rows):
    assert not any(r.raw.startswith("#") for r in rows.values())
    assert all(r.raw for r in rows.values())


def test_plain_name_is_one_subject_no_steer(rows):
    assert rows["Arboliva"].subjects == ("Arboliva",)
    assert rows["Arboliva"].steer == ""


def test_ampersand_and_lines_word(rows):
    assert rows["Krabby & Corphish lines"].subjects == ("Krabby", "Corphish")


def test_comma_ends_subjects(rows):
    row = rows["Sableye, mrror Mawile's viability"]
    assert row.subjects == ("Sableye",)
    assert row.steer == "mrror Mawile's viability"


def test_dash_ends_subjects(rows):
    assert rows["Absol - 540 BST"].subjects == ("Absol",)
    assert rows["Absol - 540 BST"].steer == "540 BST"


def test_non_species_word_ends_subjects(rows):
    row = rows["Alakazam mirroed BST w Gengar & Machamp & Golem (3 stage trade evos all 530 BST)"]
    assert row.subjects == ("Alakazam",)
    assert row.steer.startswith("mirroed BST w Gengar")


def test_plan_example_row(rows):
    row = rows["Mandibuzz line & Braviary line together, mirrored"]
    assert row.subjects == ("Mandibuzz", "Braviary")
    assert row.steer == "together, mirrored"


def test_regional_prefix_rewrites(rows, snapshot, names):
    assert rows["Alolan Ninetales"].subjects == ("Ninetales Alola",)
    (resolved,) = _resolve("Alolan Ninetales", rows, snapshot, names)
    assert resolved.id == "ninetalesalola"
    assert resolved.line == ["vulpixalola", "ninetalesalola"]


def test_subject_walks_to_final_stage(rows, snapshot, names):
    (k, c) = _resolve("Krabby & Corphish lines", rows, snapshot, names)
    assert (k.id, c.id) == ("kingler", "crawdaunt")
    assert k.line == ["krabby", "kingler"]
    assert k.group == c.group == "kingler+crawdaunt"


def test_three_stage_line_and_no_group(rows, snapshot, names):
    (r,) = _resolve("Blissey", rows, snapshot, names)
    assert r.line == ["happiny", "chansey", "blissey"]
    assert r.group is None


def test_forms_are_megas_of_the_final(rows, snapshot, names):
    (r,) = _resolve("Absol - 540 BST", rows, snapshot, names)
    assert r.forms == ["absolmega"]
    assert r.steer == "540 BST"


def test_steer_species_become_references(rows, snapshot, names):
    (r,) = _resolve(
        "Alakazam mirroed BST w Gengar & Machamp & Golem (3 stage trade evos all 530 BST)",
        rows, snapshot, names,
    )
    assert r.references == ["gengar", "machamp", "golem"]
    (s,) = _resolve("Sableye, mrror Mawile's viability", rows, snapshot, names)
    assert s.references == ["mawile"]


def test_branching_pre_evo_is_rejected_with_finals(rows, snapshot, names):
    result = _resolve("Eevee", rows, snapshot, names)
    assert isinstance(result, q.Unresolved)
    assert "Vaporeon" in result.reason and "Sylveon" in result.reason


def test_unknown_name_is_unresolved(rows, snapshot, names):
    result = _resolve("Notamon", rows, snapshot, names)
    assert isinstance(result, q.Unresolved)
    assert result.row == "Notamon"


def test_typo_gets_a_close_match_hint(rows, snapshot, names):
    result = _resolve("Beeheeyem", rows, snapshot, names)
    assert isinstance(result, q.Unresolved)
    assert "Beheeyem" in result.reason


def test_hint_names_the_display_name_not_the_id(snapshot, names):
    # Kommo-o's id is `kommoo` but its display name is `Kommo O`; only the name resolves.
    (row,) = q.parse_rows("Kommo-o line, redo", names)
    result = q.resolve_row(row, snapshot, names)
    assert isinstance(result, q.Unresolved)
    assert "'Kommo O'" in result.reason
