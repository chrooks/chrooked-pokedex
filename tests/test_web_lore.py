"""Tests for the lore fetch adapter. Hermetic: every request is served by an
``httpx.MockTransport`` replaying the captured fixtures, so nothing leaves the
machine and the suite stays offline-safe.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from chrooked_pokedex.web.lore import (
    BULBAPEDIA_API,
    HttpLoreProvider,
    LoreError,
    LoreResult,
    NullLoreProvider,
)

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).parent / "fixtures" / "lore"
_KNOWN = {"glalie", "marowak", "goodra"}


def _fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text("utf-8"))


# Ids PokeAPI actually serves a species page for. Deliberately excludes
# `marowakalola`: the real API 404s on every form id even when the form is its
# own species in our dex, and that 404 is what drives the base-species fallback.
_POKEAPI_HAS = {"glalie", "marowak", "goodra"}


def _handler(calls: list[httpx.Request], *, pokeapi_status: int = 200):
    """Serve the captured Glalie payloads, recording every request made."""

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        url = str(request.url)
        if "pokeapi.co" in url:
            if pokeapi_status != 200:
                return httpx.Response(pokeapi_status)
            if request.url.path.rsplit("/", 1)[-1] not in _POKEAPI_HAS:
                return httpx.Response(404)
            return httpx.Response(200, json=_fixture("pokeapi-glalie.json"))
        if BULBAPEDIA_API in url:
            params = request.url.params
            if params.get("prop") == "sections":
                return httpx.Response(200, json=_fixture("bulba-glalie-sections.json"))
            section = params.get("section")
            if section == "47":
                return httpx.Response(
                    200, json=_fixture("bulba-glalie-name-origin.json")
                )
            if section == "46":
                return httpx.Response(200, json=_fixture("bulba-glalie-origin.json"))
            return httpx.Response(404)
        return httpx.Response(404)

    return handle


def _provider(tmp_path: Path, calls: list[httpx.Request], **kwargs) -> HttpLoreProvider:
    client = httpx.Client(transport=httpx.MockTransport(_handler(calls, **kwargs)))
    return HttpLoreProvider(
        known_species=_KNOWN, cache_dir=tmp_path / "lore", client=client
    )


# --------------------------------------------------------------------------- #
# The happy path — the fact that started all this must come back
# --------------------------------------------------------------------------- #


def test_fetching_glalie_returns_real_lore_including_the_goalie_etymology(
    tmp_path: Path,
) -> None:
    calls: list[httpx.Request] = []
    result = _provider(tmp_path, calls).fetch("glalie", "Glalie")

    assert result.found is True
    assert result.genus == "Face Pokémon"
    assert len(result.dex_entries) == 15
    # THE regression: the model claimed "glace, French for ice". The real
    # etymology now arrives as fetched text.
    assert "goalie" in result.name_origin
    assert "glacier" in result.name_origin
    assert "glace" not in result.name_origin.lower()
    # And the origin section carries the oni reading that supports Ice/Dark.
    assert "oni" in result.origin


def test_the_etymology_is_not_injected_twice(tmp_path: Path) -> None:
    # MediaWiki returns a section WITH its subsections, and "Name origin" is a
    # child of "Origin" — so the goalie paragraph arrived in both fields and paid
    # for the character budget twice.
    result = _provider(tmp_path, []).fetch("glalie", "Glalie")
    assert "goalie" in result.name_origin
    assert "goalie" not in result.origin
    # The parent section keeps its own content.
    assert "Namahage" in result.origin


def test_sources_name_both_upstreams(tmp_path: Path) -> None:
    result = _provider(tmp_path, []).fetch("glalie", "Glalie")
    assert any("pokeapi.co" in s for s in result.sources)
    assert any("bulbapedia" in s for s in result.sources)
    assert len(result.sources) == 2


def test_section_indices_are_discovered_not_hardcoded(tmp_path: Path) -> None:
    # Glalie's Origin is section 46 and Name origin is 47 on THIS page only. The
    # adapter must read the section list first and match by title.
    calls: list[httpx.Request] = []
    _provider(tmp_path, calls).fetch("glalie", "Glalie")
    bulba = [c for c in calls if BULBAPEDIA_API in str(c.url)]
    assert bulba[0].url.params.get("prop") == "sections"
    fetched = {c.url.params.get("section") for c in bulba[1:]}
    assert fetched == {"46", "47"}


# --------------------------------------------------------------------------- #
# Forms
# --------------------------------------------------------------------------- #


def test_a_form_falls_back_to_its_base_species_after_a_404(tmp_path: Path) -> None:
    """The 404 drives the fallback, not a guess made up front.

    A canon regional form is its own species in the base snapshot, so "is this a
    known species" cannot tell you whether PokeAPI holds a page for it — and it
    does not. The adapter asks for the form, takes the 404, then asks for the base.
    """
    calls: list[httpx.Request] = []
    result = _provider(tmp_path, calls).fetch("marowakalola", "Marowak")
    assert result.found is True
    assert result.base_species == "marowak"
    asked = [c.url.path.rsplit("/", 1)[-1] for c in calls if "pokeapi.co" in str(c.url)]
    assert asked == ["marowakalola", "marowak"]


def test_a_species_with_its_own_page_never_falls_back(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    result = _provider(tmp_path, calls).fetch("glalie", "Glalie")
    assert result.base_species == "glalie"
    asked = [c.url.path.rsplit("/", 1)[-1] for c in calls if "pokeapi.co" in str(c.url)]
    assert asked == ["glalie"]  # exactly one request, no speculative second


# --------------------------------------------------------------------------- #
# Misses and failures — a missing page is data, a broken network is an error
# --------------------------------------------------------------------------- #


def test_a_species_in_no_source_reports_not_found_rather_than_raising(
    tmp_path: Path,
) -> None:
    # A bespoke species: PokeAPI 404s and the wiki has no page. This is an
    # ordinary outcome in this Ruleset, not an error.
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handle))
    provider = HttpLoreProvider(
        known_species=_KNOWN, cache_dir=tmp_path / "lore", client=client
    )
    result = provider.fetch("palossandicyaevian", "Palossand")
    assert result.found is False
    assert result.sources == ()


def test_an_upstream_server_error_raises_lore_error(tmp_path: Path) -> None:
    with pytest.raises(LoreError):
        _provider(tmp_path, [], pokeapi_status=500).fetch("glalie", "Glalie")


def test_a_dead_network_raises_lore_error(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    provider = HttpLoreProvider(
        known_species=_KNOWN, cache_dir=tmp_path / "lore", client=client
    )
    with pytest.raises(LoreError):
        provider.fetch("glalie", "Glalie")


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #


def test_a_second_fetch_makes_no_http_request(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    provider = _provider(tmp_path, calls)
    first = provider.fetch("glalie", "Glalie")
    count_after_first = len(calls)
    assert count_after_first > 0

    second = provider.fetch("glalie", "Glalie")
    assert len(calls) == count_after_first  # nothing new left the machine
    assert second.name_origin == first.name_origin
    assert second.dex_entries == first.dex_entries


def test_the_cache_is_keyed_by_the_requested_id_not_the_resolved_one(
    tmp_path: Path,
) -> None:
    """Two forms of one base must not inherit each other's label.

    Caching under the resolved base would serve `marowakalola`'s entry — labelled
    as base-species lore — to a later request for `marowak` itself, which has its
    own page and needs no label. One extra fetch per form is the cheaper mistake.
    """
    calls: list[httpx.Request] = []
    provider = _provider(tmp_path, calls)
    base = provider.fetch("marowak", "Marowak")
    n = len(calls)
    form = provider.fetch("marowakalola", "Marowak")

    assert len(calls) > n  # its own entry, its own fetch
    assert base.base_species == "marowak"
    assert form.base_species == "marowak"
    # And the form's own entry is reused on a repeat.
    m = len(calls)
    provider.fetch("marowakalola", "Marowak")
    assert len(calls) == m


def test_a_corrupt_cache_entry_is_a_miss_not_a_crash(tmp_path: Path) -> None:
    cache_dir = tmp_path / "lore"
    cache_dir.mkdir(parents=True)
    (cache_dir / "glalie.json").write_text("{not json", encoding="utf-8")
    result = _provider(tmp_path, []).fetch("glalie", "Glalie")
    assert result.found is True


def test_a_pre_regional_fix_cache_entry_is_a_miss(tmp_path: Path) -> None:
    """v1 entries cached base-species lore under regional ids; they must refetch."""
    cache_dir = tmp_path / "lore"
    cache_dir.mkdir(parents=True)
    stale = {"result": {"found": True, "dex_entries": ["STALE"], "base_species": "glalie"}}
    (cache_dir / "glalie.json").write_text(json.dumps(stale), encoding="utf-8")
    result = _provider(tmp_path, []).fetch("glalie", "Glalie")
    assert "STALE" not in result.dex_entries


# --------------------------------------------------------------------------- #
# Regional forms — their own lore, never the base form's
# --------------------------------------------------------------------------- #

_NINETALES_SECTIONS = {
    "parse": {
        "sections": [
            {"index": "2", "line": "Forms"},
            {"index": "6", "line": "Pokédex entries"},
            {"index": "65", "line": "Origin"},
            {"index": "66", "line": "Name origin"},
        ]
    }
}
_NINETALES_WIKITEXT = {
    "2": (
        "===Forms===\n[[File:Alolan Ninetales SM concept art.jpg|thumb|250px|left|Art]]\n"
        "Ninetales has a [[regional form]]: {{rf|Alolan}} Ninetales.\n\n"
        "Alolan Ninetales lives on Alola's snow-capped [[Mount Lanakila]].\n{{left clear}}"
    ),
    "6": (
        "===Pokédex entries===\n{{Dex/Gen/3|gen=VII|reg1=Alola}}\n"
        "{{Dex/Entry1|v=Sun|entry=Legend has it that this mystical Pokémon was formed "
        "when nine saints coalesced into one.}}\n"
        "{{Dex/Form|Alolan Form}}\n"
        "{{Dex/Entry1|v=Sun|entry=It creates drops of ice in its coat.}}\n"
        "|}\n|}\n{{Dex/Gen/5|gen=VIII}}\n"
        "{{Dex/Entry1|v=Sword|t=FFF|entry=Grabbing one of its tails could result in a curse.}}\n"
        "{{Dex/Form|Alolan Form}}\n"
        "{{Dex/Entry1|v=Sword|t=FFF|entry=A deity resides in the snowy mountains.}}\n|}"
    ),
    "65": (
        "===Origin===\nNinetales is based on a {{wp|fox}} and the ''{{wp|kitsune}}''.\n\n"
        "Alolan Ninetales may be based on an {{wp|Arctic fox}}."
    ),
    "66": "====Name origin====\nNinetales may be a combination of ''nine'' and ''tales''.",
}


def _ninetales_provider(tmp_path: Path, calls: list[httpx.Request]) -> HttpLoreProvider:
    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "pokeapi.co" in str(request.url):
            if request.url.path.endswith("/ninetales"):
                # PokeAPI's Sun/Moon text for the base species is the KANTO fox.
                return httpx.Response(200, json={
                    "genera": [{"genus": "Fox Pokémon", "language": {"name": "en"}}],
                    "flavor_text_entries": [{
                        "flavor_text": "Very vengeful. A 1,000-year curse.",
                        "language": {"name": "en"},
                        "version": {"name": "sun"},
                    }],
                })
            return httpx.Response(404)
        section = request.url.params.get("section")
        if section is None:
            return httpx.Response(200, json=_NINETALES_SECTIONS)
        return httpx.Response(
            200, json={"parse": {"wikitext": {"*": _NINETALES_WIKITEXT[section]}}}
        )

    client = httpx.Client(transport=httpx.MockTransport(handle))
    return HttpLoreProvider(
        known_species={"ninetales", "ninetalesalola"},
        cache_dir=tmp_path / "lore",
        client=client,
    )


def test_a_regional_form_gets_its_own_lore_not_the_base_forms(tmp_path: Path) -> None:
    """ninetalesalola once read as the Kanto Fire fox and inferred Fire/Psychic."""
    calls: list[httpx.Request] = []
    # The dex display name; Bulbapedia has no "Ninetales Alola (Pokémon)" page.
    result = _ninetales_provider(tmp_path, calls).fetch("ninetalesalola", "Ninetales Alola")

    pages = {c.url.params.get("page") for c in calls if "pokeapi.co" not in str(c.url)}
    assert pages == {"Ninetales (Pokémon)"}

    assert result.dex_entries == (
        "It creates drops of ice in its coat.",
        "A deity resides in the snowy mountains.",
    )
    assert "Mount Lanakila" in result.origin
    assert "Arctic fox" in result.origin
    assert "kitsune" not in result.origin  # the base form's paragraph is dropped
    assert "thumb" not in result.origin and "clear" not in result.origin
    assert "nine" in result.name_origin  # the name is shared, so it stays
    assert result.genus == "Fox Pokémon"
    # It describes the form itself now, so no BASE label is rendered.
    assert result.base_species == "ninetalesalola"


def test_the_base_species_does_not_read_regional_sections(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    result = _ninetales_provider(tmp_path, calls).fetch("ninetales", "Ninetales")
    assert result.dex_entries == ("Very vengeful. A 1,000-year curse.",)
    assert "kitsune" in result.origin
    fetched = {c.url.params.get("section") for c in calls}
    assert fetched == {None, "65", "66"}


# --------------------------------------------------------------------------- #
# The null provider and the Port contract
# --------------------------------------------------------------------------- #


def test_null_provider_finds_nothing_and_satisfies_the_port() -> None:
    from chrooked_pokedex.web.lore import LoreProvider

    provider = NullLoreProvider()
    assert isinstance(provider, LoreProvider)
    result = provider.fetch("glalie", "Glalie")
    assert result == LoreResult(found=False, base_species="glalie")


def test_the_http_provider_satisfies_the_port() -> None:
    from chrooked_pokedex.web.lore import LoreProvider

    assert isinstance(HttpLoreProvider(), LoreProvider)


def test_chars_counts_every_piece_of_text() -> None:
    result = LoreResult(
        found=True, genus="ab", dex_entries=("cde", "fg"), origin="h", name_origin="ij"
    )
    assert result.chars == 2 + 3 + 2 + 1 + 2


def test_a_punctuated_name_asks_both_upstreams_by_its_canon_spelling(tmp_path: Path) -> None:
    """The dex says "Kommo O"; PokeAPI wants `kommo-o` and Bulbapedia "Kommo-o"."""
    calls: list[httpx.Request] = []
    _provider(tmp_path, calls).fetch("kommoo", "Kommo O")
    asked = [c.url.path.rsplit("/", 1)[-1] for c in calls if "pokeapi.co" in str(c.url)]
    pages = {c.url.params.get("page") for c in calls if BULBAPEDIA_API in str(c.url)}
    assert asked == ["kommo-o"]
    assert pages == {"Kommo-o (Pokémon)"}
