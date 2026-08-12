"""Unit tests for the pure lore text functions, against captured real payloads.

Fixtures under ``tests/fixtures/lore/`` are verbatim responses recorded on
2026-08-12 from PokeAPI and Bulbapedia's MediaWiki API. Testing against the real
shapes is the whole point: the template trap below only shows up in real
Bulbapedia markup, and a hand-written sample would have hidden it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chrooked_pokedex.web.lore_text import (
    NOT_FOUND_BLOCK,
    base_species_id,
    clean_wikitext,
    pokeapi_lore,
    render_lore,
    truncate_at_sentence,
)

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).parent / "fixtures" / "lore"


def _wikitext(name: str) -> str:
    payload = json.loads((_FIXTURES / name).read_text("utf-8"))
    return payload["parse"]["wikitext"]["*"]


# --------------------------------------------------------------------------- #
# base_species_id — PokeAPI 404s on every form id, so forms map to their base
# --------------------------------------------------------------------------- #


def test_a_known_species_maps_to_itself() -> None:
    assert base_species_id("glalie", {"glalie", "marowak"}) == "glalie"


def test_a_form_maps_to_its_base_species() -> None:
    known = {"marowak", "goodra", "glalie"}
    assert base_species_id("marowakalola", known) == "marowak"
    assert base_species_id("goodrahisui", known) == "goodra"
    assert base_species_id("glaliemega", known) == "glalie"


def test_the_longest_matching_base_wins() -> None:
    # 'ho' must not swallow 'hooh' — the longest prefix is the right base.
    assert base_species_id("hoohmega", {"ho", "hooh"}) == "hooh"


def test_an_unknown_id_is_returned_unchanged() -> None:
    # A bespoke species is in no source; the caller turns the miss into
    # NOT_FOUND rather than this function guessing at a base.
    assert base_species_id("palossandicyaevian", {"glalie"}) == "palossandicyaevian"


# --------------------------------------------------------------------------- #
# clean_wikitext — the regression test this module exists for
# --------------------------------------------------------------------------- #


def test_cleaning_keeps_the_words_inside_templates() -> None:
    """THE trap. Real markup reads:

        a combination of ''{{wp|glacier}}'' and ''{{wp|Goaltender|goalie}}''

    Dropping templates wholesale yields "a combination of and" — the etymology
    vanishes and the model gets a sentence with a hole in it. That is how the
    fabricated "glace, French for ice" survived review in the first place.
    """
    cleaned = clean_wikitext(_wikitext("bulba-glalie-name-origin.json"))
    assert "glacier" in cleaned
    assert "goalie" in cleaned
    assert "combination of glacier and goalie" in cleaned


def test_cleaning_keeps_the_display_arg_of_a_two_arg_template() -> None:
    # {{wp|Goaltender|goalie}} shows "goalie", not "Goaltender".
    assert clean_wikitext("a {{wp|Goaltender|goalie}} mask") == "a goalie mask"


def test_cleaning_keeps_a_single_arg_template() -> None:
    assert clean_wikitext("an ''{{wp|oni}}'' or {{wp|Tsurube-otoshi}}") == (
        "an oni or Tsurube-otoshi"
    )


def test_cleaning_handles_a_template_glued_to_following_text() -> None:
    # "{{wp|hail}}stone" must render "hailstone", not "hail stone".
    assert clean_wikitext("resembles a {{wp|hail}}stone.") == "resembles a hailstone."


def test_cleaning_unwinds_nested_templates() -> None:
    assert clean_wikitext("x {{outer|{{inner|kept}}}} y") == "x kept y"


def test_cleaning_drops_citations_entirely() -> None:
    cleaned = clean_wikitext(_wikitext("bulba-glalie-name-origin.json"))
    assert "bsky.app" not in cleaned
    assert "<ref" not in cleaned
    # The sentence the citation hung off survives.
    assert "goalie mask" in cleaned


def test_cleaning_resolves_both_link_forms_and_drops_headings() -> None:
    cleaned = clean_wikitext(_wikitext("bulba-glalie-origin.json"))
    assert "===" not in cleaned
    assert "Origin" not in cleaned.splitlines()[0]
    assert "rice ball" in cleaned  # [[rice ball]]
    assert "ice hockey mask" in cleaned  # {{wp|goaltender mask|ice hockey mask}}
    assert "[[" not in cleaned and "{{" not in cleaned


def test_cleaning_the_origin_section_keeps_the_oni_reading() -> None:
    # The demon reading is what supports an Ice/Dark redesign; it must survive.
    cleaned = clean_wikitext(_wikitext("bulba-glalie-origin.json"))
    assert "oni" in cleaned
    assert "Namahage" in cleaned


# --------------------------------------------------------------------------- #
# pokeapi_lore
# --------------------------------------------------------------------------- #


def test_pokeapi_lore_pulls_genus_and_dedupes_entries() -> None:
    payload = json.loads((_FIXTURES / "pokeapi-glalie.json").read_text("utf-8"))
    genus, entries = pokeapi_lore(payload)
    assert genus == "Face Pokémon"
    # 25 English entries in the payload collapse to 15 unique ones.
    assert len(entries) == 15
    assert len(set(entries)) == len(entries)
    # The ecology the redesign leans on survives the cleanup.
    assert any("freeze" in e.lower() for e in entries)
    # Line breaks and form feeds from the original text boxes are gone.
    assert not any("\n" in e or "\f" in e for e in entries)


def test_pokeapi_lore_ignores_non_english_entries() -> None:
    payload = {
        "genera": [
            {"genus": "Kopf", "language": {"name": "de"}},
            {"genus": "Face Pokémon", "language": {"name": "en"}},
        ],
        "flavor_text_entries": [
            {"flavor_text": "Deutsch", "language": {"name": "de"}},
            {"flavor_text": "English", "language": {"name": "en"}},
        ],
    }
    assert pokeapi_lore(payload) == ("Face Pokémon", ("English",))


def test_pokeapi_lore_tolerates_a_thin_payload() -> None:
    # A species page with no genus and no entries is an ordinary outcome.
    assert pokeapi_lore({}) == ("", ())


# --------------------------------------------------------------------------- #
# truncate_at_sentence
# --------------------------------------------------------------------------- #


def test_short_text_is_untouched() -> None:
    assert truncate_at_sentence("One. Two.", 100) == "One. Two."


def test_truncation_prefers_a_sentence_boundary() -> None:
    text = "A" * 60 + ". " + "B" * 60 + "."
    out = truncate_at_sentence(text, 80)
    assert out.endswith(".")
    assert "B" not in out


def test_truncation_marks_a_hard_cut_when_no_boundary_is_near() -> None:
    out = truncate_at_sentence("C" * 200, 50)
    assert out.endswith("[…truncated]")


# --------------------------------------------------------------------------- #
# render_lore — what actually lands in the prompt
# --------------------------------------------------------------------------- #


def test_not_found_renders_the_refusal_block() -> None:
    block = render_lore(
        found=False, genus="", dex_entries=(), origin="", name_origin=""
    )
    assert block == NOT_FOUND_BLOCK
    assert "Do NOT invent" in block


def test_a_found_block_carries_every_section() -> None:
    block = render_lore(
        found=True,
        genus="Face Pokémon",
        dex_entries=("It freezes prey solid.",),
        origin="Based on an oni mask.",
        name_origin="glacier + goalie",
    )
    assert "Category: Face Pokémon" in block
    assert "- It freezes prey solid." in block
    assert "Design origin: Based on an oni mask." in block
    assert "Name origin: glacier + goalie" in block


def test_base_species_lore_is_labelled_as_such() -> None:
    # Marowak's dex text is not a description of Alolan Marowak. The label is
    # what stops the model asserting base-species detail as form truth.
    block = render_lore(
        found=True,
        genus="Bone Keeper Pokémon",
        dex_entries=("It lives in the desert.",),
        origin="",
        name_origin="",
        requested_id="marowakalola",
        base_species="marowak",
    )
    assert "BASE species 'marowak'" in block
    assert "not the form 'marowakalola'" in block


def test_no_label_when_the_species_was_found_directly() -> None:
    block = render_lore(
        found=True,
        genus="Face Pokémon",
        dex_entries=("x",),
        origin="",
        name_origin="",
        requested_id="glalie",
        base_species="glalie",
    )
    assert "BASE species" not in block


def test_the_block_respects_the_cap() -> None:
    block = render_lore(
        found=True,
        genus="G",
        dex_entries=tuple(f"Entry number {i}." for i in range(500)),
        origin="",
        name_origin="",
        cap=500,
    )
    assert len(block) <= 500
