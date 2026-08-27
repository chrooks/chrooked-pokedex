"""The blind-design anonymizer: names, dex numbers, and franchise markers out;
real-world biology and myth kept, because that is what a blind pass reasons from.
"""
from __future__ import annotations

import pytest

from chrooked_pokedex.web.lore_anon import OTHER, SUBJECT, anonymize_lore, anonymize_text

pytestmark = pytest.mark.unit


def test_subject_name_becomes_a_generic_referent() -> None:
    out = anonymize_text("Ariados spins string.", subject_names=["Ariados"])
    assert "Ariados" not in out
    assert SUBJECT in out


def test_other_species_names_are_redacted_separately() -> None:
    out = anonymize_text(
        "Ariados waits for Cutiefly.", subject_names=["Ariados"], other_names=["Cutiefly"]
    )
    assert "Cutiefly" not in out
    assert OTHER in out
    assert SUBJECT in out


def test_dex_numbers_go() -> None:
    for raw in ("No. 168 is a spider.", "#168 is a spider.", "№ 168 is a spider."):
        assert "168" not in anonymize_text(raw)


def test_franchise_and_mega_markers_go() -> None:
    out = anonymize_text("This POKéMON evolves. Mega Beedrill is stronger.")
    assert "POKéMON" not in out and "Pokémon" not in out
    assert "Mega" not in out


def test_name_matching_is_case_sensitive_so_ordinary_words_survive() -> None:
    """Ditto and Golem are species names AND English words."""
    out = anonymize_text("a golem of rock, and ditto for the others", subject_names=["Golem", "Ditto"])
    assert out == "a golem of rock, and ditto for the others"


def test_longest_name_wins_so_multiword_names_are_not_split() -> None:
    out = anonymize_text("Mr. Mime blocks it.", subject_names=["Mr. Mime", "Mime"])
    assert "Mime" not in out


def test_name_origin_is_dropped_entirely() -> None:
    """Etymology's whole job is to name the creature; nothing in it is salvageable."""
    out = anonymize_lore(
        genus="Long Leg",
        dex_entries=("It spins thread.",),
        origin="Based on a spider.",
    )
    assert out["name_origin"] == ""


def test_design_origin_is_kept_because_it_is_the_design_material() -> None:
    out = anonymize_lore(
        genus="",
        dex_entries=(),
        origin="Based on the Myrmarachne formicaria spider, with the body reversed.",
    )
    assert "Myrmarachne" in str(out["origin"])


def test_empty_input_is_safe() -> None:
    assert anonymize_text("") == ""
    out = anonymize_lore(genus="", dex_entries=(), origin="")
    assert out["dex_entries"] == ()


def test_redaction_does_not_leave_doubled_spaces_or_floating_punctuation() -> None:
    out = anonymize_text("It is a Pokémon .  Truly.", subject_names=[])
    assert "  " not in out
    assert " ." not in out


def test_the_renderers_own_section_label_is_scrubbed() -> None:
    """The label 'Pokedex entries:' is injected by render_lore, not fetched, so
    it never passed through anonymize_lore. A live blind run leaked it."""
    block = "Researched lore (read this; do not contradict it):\nPokedex entries:\n- It spins silk."
    out = anonymize_text(block)
    assert "Pokedex" not in out
    assert "It spins silk" in out


def test_game_title_citations_go_in_either_casing() -> None:
    """'per its Sun Pokedex entry' leaked past a capital-I-only pattern."""
    assert "Sun" not in anonymize_text("based on a spider, per its Sun Pokedex entry.")
    assert "Sun" not in anonymize_text("Its Sun Pokedex entry says so.")
    assert "Sword" not in anonymize_text("Its Sword and Shield Pokedex entry.")
