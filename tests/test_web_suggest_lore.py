"""Issue #77 — researched lore injected into the two heavy suggest capabilities.

Proved at the HTTP routes (seam 1), with BOTH Ports faked: the LLM Port records
the prompt it was handed, and the lore Port records what it was asked for. The
load-bearing assertion in nearly every test here is on the captured prompt, not
on the fetch — a fetch that never reaches the model buys the author nothing, and
that distinction is the whole point of the milestone.

Hermetic: no network, no key, no `litellm`.

- lore is OFF by default, and an unrecognized mode is off too (a typo in a request
  body is not consent to start making network calls).
- With it on, the fetched text lands in the USER context, never in the rubric —
  the rubric is the cache-stable prefix shared across species.
- A miss states the absence AND adds the do-not-invent line to the rubric, which
  is the correctness linchpin: silence is what let the model fabricate.
- `condensed` makes exactly one extra bounded call; a failing condenser degrades
  to the raw block and says so in provenance rather than costing a suggestion.
- Every response carries provenance, and a lore-on call ledgers one line.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex import ledger as ledgermod
from chrooked_pokedex.web import llm as llmmod
from chrooked_pokedex.web import lore as loremod
from chrooked_pokedex.web import lore_text
from chrooked_pokedex.web.app import create_app

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"

_SNAPSHOT: dict[str, Any] = {
    "version": "1.11.2",
    "species": {
        "goodra": {
            "dex": 706,
            "chrooked_id": "goodra",
            "name": "Goodra",
            "types": ["Dragon"],
            "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
            "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
            "learnset": [{"level": 1, "move": "Tackle"}],
        },
        # A form whose dex text lives only under its base species — the case the
        # base-species label exists for.
        "marowakalola": {
            "dex": 105,
            "chrooked_id": "marowakalola",
            "name": "Marowak",
            "types": ["Fire", "Ghost"],
            "abilities": {"primary": "Rough Skin", "secondary": None, "hidden": None},
            "stats": {"hp": 60, "atk": 80, "def": 110, "spa": 50, "spd": 80, "spe": 45},
            "learnset": [{"level": 1, "move": "Tackle"}],
        },
    },
    "abilities": {
        "sap-sipper": {"chrooked_id": "sap-sipper", "name": "Sap Sipper", "description": "x", "aka": {}},
        "gooey": {"chrooked_id": "gooey", "name": "Gooey", "description": "x", "aka": {}},
        "rough-skin": {"chrooked_id": "rough-skin", "name": "Rough Skin", "description": "x", "aka": {}},
    },
    "moves": {},
    "type_chart": [
        {"attacker": "Water", "defender": "Fire", "multiplier": 2.0},
        {"attacker": "Dragon", "defender": "Dragon", "multiplier": 2.0},
        {"attacker": "Poison", "defender": "Grass", "multiplier": 2.0},
    ],
}

# A phrase that appears in no rubric and no species context, so finding it in a
# prompt can only mean the fetched lore got there.
_SENTINEL = "coined because the creature looks like a GOALIE MASK"
_CONDENSED = "Brief: ice creature, name from glacier plus goalie."

_FOUND = loremod.LoreResult(
    found=True,
    genus="Face Pokémon",
    dex_entries=("It freezes prey solid and eats it later.",),
    origin="Based on a hailstone spirit.",
    name_origin=_SENTINEL,
    sources=("https://pokeapi.co/api/v2/pokemon-species/glalie", "https://bulbapedia.example/Glalie"),
    base_species="goodra",
)

_ABILITY_RESULT = {
    "draft": {"abilities": {"hidden": "Rough Skin"}},
    "rationale": {"hidden": "Punishes contact."},
    "alternatives": [],
}

_OPTIONS_RESULT = {
    "draft": {
        "options": [
            {"types": ["Water", "Dragon"], "role": "bulky attacker", "rationale": "slug"},
            {"types": ["Poison", "Dragon"], "role": "stall pivot", "rationale": "venom"},
        ]
    },
    "rationale": {"options": "A gentle amphibious slug."},
}


class _FakeProvider:
    """The LLM Port, recording every call so a test can read the real prompt.

    A condense call is told apart by its schema (the one-field ``lore`` object),
    which is also how the count proves "exactly one extra call".
    """

    def __init__(
        self,
        result: dict[str, Any],
        *,
        condensed: str = _CONDENSED,
        condense_fails: bool = False,
    ) -> None:
        self.result = result
        self.condensed = condensed
        self.condense_fails = condense_fails
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if "lore" in (kwargs["schema"].get("properties") or {}):
            if self.condense_fails:
                raise llmmod.LlmError("The LLM provider call failed: APIError.")
            return {"lore": self.condensed}
        return self.result

    @property
    def suggest_calls(self) -> list[dict[str, Any]]:
        """Only the capability calls — the condense call is not a suggestion."""
        return [c for c in self.calls if "lore" not in (c["schema"].get("properties") or {})]


class _FakeLoreProvider:
    """The lore Port, recording what it was asked for and returning a canned result."""

    def __init__(self, result: loremod.LoreResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def fetch(self, chrooked_id: str, species_name: str) -> loremod.LoreResult:
        self.calls.append((chrooked_id, species_name))
        return self.result


class _FailingLoreProvider:
    """A lore Port whose lookup itself failed — the degrade-don't-die path."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def fetch(self, chrooked_id: str, species_name: str) -> loremod.LoreResult:
        self.calls.append((chrooked_id, species_name))
        raise loremod.LoreError("lore fetch failed for https://pokeapi.co: timeout")


@pytest.fixture(autouse=True)
def _no_condense_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the condense call on the injected mock, whatever the real env holds."""
    monkeypatch.delenv("LLM_CONDENSE_MODEL", raising=False)


@pytest.fixture
def ruleset_dir(tmp_path: Path) -> Path:
    dst = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, dst)
    return dst


def _client(
    ruleset_dir: Path,
    tmp_path: Path,
    provider: Any = None,
    lore_provider: Any = None,
) -> TestClient:
    snap_path = tmp_path / "1.11.2.json"
    snap_path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(
        ruleset_dir=ruleset_dir,
        snapshot_path=snap_path,
        llm_provider=provider,
        lore_provider=lore_provider,
    )
    return TestClient(app, raise_server_exceptions=False)


def _ability(client: TestClient, body: dict[str, Any] | None = None, species: str = "goodra"):
    return client.post(f"/api/species/{species}/suggest/ability", json=body)


def _options(client: TestClient, body: dict[str, Any]):
    return client.post("/api/species/goodra/suggest/typing", json={"mode": "lore-options", **body})


# --------------------------------------------------------------------------- #
# ac1 — off by default, and inert when off
# --------------------------------------------------------------------------- #


def test_ability_without_lore_field_never_fetches(ruleset_dir: Path, tmp_path: Path) -> None:
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FakeLoreProvider(_FOUND)
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _ability(client)

    assert response.status_code == 200
    assert lore.calls == []
    assert "Researched lore" not in llm.calls[0]["user"]
    assert _SENTINEL not in llm.calls[0]["user"]
    assert response.json()["lore"] == {"mode": "off"}


def test_lore_off_context_is_unchanged(ruleset_dir: Path, tmp_path: Path) -> None:
    """The off prompt is byte-identical to the one an explicit off request builds.

    Both go through the new code path, so this pins that the path adds nothing at
    all when it is not asked to — not a shortened block, not a blank line.
    """
    absent = _FakeProvider(_ABILITY_RESULT)
    explicit = _FakeProvider(_ABILITY_RESULT)
    no_port = _FakeProvider(_ABILITY_RESULT)
    _ability(_client(ruleset_dir, tmp_path, absent, _FakeLoreProvider(_FOUND)))
    _ability(
        _client(ruleset_dir, tmp_path, explicit, _FakeLoreProvider(_FOUND)),
        {"lore": "off"},
    )
    # No lore Port attached at all — the other half of "inert until asked for".
    _ability(_client(ruleset_dir, tmp_path, no_port, None))

    prompts = {(c.calls[0]["system"], c.calls[0]["user"]) for c in (absent, explicit, no_port)}
    assert len(prompts) == 1


def test_lore_options_without_lore_field_never_fetches(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    llm = _FakeProvider(_OPTIONS_RESULT)
    lore = _FakeLoreProvider(_FOUND)
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _options(client, {})

    assert response.status_code == 200
    assert lore.calls == []
    assert "Researched lore" not in llm.calls[0]["user"]
    assert response.json()["lore"] == {"mode": "off"}


# --------------------------------------------------------------------------- #
# ac2 — an unrecognized mode is off
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", ["yes", "FULL", "", "true", 1, None])
def test_unrecognized_mode_fetches_nothing(
    ruleset_dir: Path, tmp_path: Path, value: Any
) -> None:
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FakeLoreProvider(_FOUND)
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _ability(client, {"lore": value})

    assert lore.calls == []
    assert response.json()["lore"] == {"mode": "off"}


# --------------------------------------------------------------------------- #
# ac3 — with lore on, the fetched text reaches the model
# --------------------------------------------------------------------------- #


def test_full_mode_puts_fetched_lore_in_the_ability_prompt(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FakeLoreProvider(_FOUND)
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _ability(client, {"lore": "full"})

    assert response.status_code == 200
    assert lore.calls == [("goodra", "Goodra")]
    user = llm.calls[0]["user"]
    assert _SENTINEL in user
    assert "Face Pokémon" in user
    # The rubric is the cache-stable prefix; per-species lore must never land in
    # it, or prompt caching is defeated for no benefit.
    assert _SENTINEL not in llm.calls[0]["system"]


def test_full_mode_puts_fetched_lore_in_the_lore_options_prompt(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    llm = _FakeProvider(_OPTIONS_RESULT)
    lore = _FakeLoreProvider(_FOUND)
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _options(client, {"lore": "full"})

    assert response.status_code == 200
    assert lore.calls == [("goodra", "Goodra")]
    assert _SENTINEL in llm.calls[0]["user"]
    assert _SENTINEL not in llm.calls[0]["system"]


# --------------------------------------------------------------------------- #
# ac4 — a form's lore is labelled as its base species'
# --------------------------------------------------------------------------- #


def test_form_lore_is_labelled_as_base_species(ruleset_dir: Path, tmp_path: Path) -> None:
    """The provider is asked for the form; what comes back is labelled honestly.

    Resolving `marowakalola` → `marowak` lives inside the HTTP adapter (it is
    driven by PokeAPI's 404, and is proved in ``tests/test_web_lore.py``), so what
    this seam owns is the label: base-species dex text must never be handed to the
    model as a description of the form.
    """
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FakeLoreProvider(
        loremod.LoreResult(
            found=True,
            genus="Bone Keeper Pokémon",
            dex_entries=("It carries the bone of its mother.",),
            sources=("https://pokeapi.co/api/v2/pokemon-species/marowak",),
            base_species="marowak",
        )
    )
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _ability(client, {"lore": "full"}, species="marowakalola")

    assert lore.calls == [("marowakalola", "Marowak")]
    user = llm.calls[0]["user"]
    assert "BASE species 'marowak'" in user
    assert "not the form 'marowakalola'" in user
    assert response.json()["lore"]["base_species"] == "marowak"


def test_real_adapter_is_seeded_with_the_snapshot_species(
    ruleset_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no fake attached, the app builds the adapter that CAN resolve a form.

    The base mapping needs the real species set; hardcoding form suffixes was the
    rejected alternative. This pins that the snapshot's ids are what gets handed in.
    """
    seen: dict[str, Any] = {}

    class _RecordingAdapter(_FakeLoreProvider):
        def __init__(self, **kwargs: Any) -> None:
            seen["known_species"] = set(kwargs.get("known_species") or ())
            super().__init__(loremod.LoreResult(found=False, base_species="goodra"))

    monkeypatch.setattr(loremod, "HttpLoreProvider", _RecordingAdapter)
    client = _client(ruleset_dir, tmp_path, _FakeProvider(_ABILITY_RESULT), None)

    _ability(client, {"lore": "full"})

    assert {"goodra", "marowakalola"} <= seen["known_species"]


# --------------------------------------------------------------------------- #
# ac5 — a miss is stated, and inventing is forbidden
# --------------------------------------------------------------------------- #


def test_not_found_states_the_absence_and_forbids_invention(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FakeLoreProvider(loremod.LoreResult(found=False, base_species="goodra"))
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _ability(client, {"lore": "full"})

    user = llm.calls[0]["user"]
    assert "NONE FOUND" in user
    assert "Do NOT invent" in user
    # The refusal instruction is the one thing that DOES join the rubric, and only
    # on a miss: without it the model reads the silence as an invitation.
    assert "LORE LOOKUP RAN AND FOUND NOTHING" in llm.calls[0]["system"]
    assert response.json()["lore"]["found"] is False


def test_lore_options_miss_carries_the_same_refusal(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    llm = _FakeProvider(_OPTIONS_RESULT)
    lore = _FakeLoreProvider(loremod.LoreResult(found=False, base_species="goodra"))
    client = _client(ruleset_dir, tmp_path, llm, lore)

    _options(client, {"lore": "full"})

    assert "NONE FOUND" in llm.calls[0]["user"]
    assert "LORE LOOKUP RAN AND FOUND NOTHING" in llm.calls[0]["system"]


def test_lore_error_degrades_instead_of_failing_the_suggestion(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FailingLoreProvider()
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _ability(client, {"lore": "full"})

    assert response.status_code == 200
    assert "Researched lore" not in llm.calls[0]["user"]
    provenance = response.json()["lore"]
    assert provenance["found"] is False
    assert "timeout" in provenance["error"]


# --------------------------------------------------------------------------- #
# ac6 — condensed makes exactly one extra call, and degrades when it fails
# --------------------------------------------------------------------------- #


def test_condensed_makes_exactly_one_extra_call(ruleset_dir: Path, tmp_path: Path) -> None:
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FakeLoreProvider(_FOUND)
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _ability(client, {"lore": "condensed"})

    assert len(llm.calls) == 2
    assert len(llm.suggest_calls) == 1
    # The condensation is injected; the raw block it replaced is not.
    user = llm.suggest_calls[0]["user"]
    assert _CONDENSED in user
    assert _SENTINEL not in user
    body = response.json()
    assert body["lore"]["mode"] == "condensed"
    assert body["lore"]["chars"] == len(_CONDENSED)


def test_failing_condenser_falls_back_to_the_raw_block(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    llm = _FakeProvider(_ABILITY_RESULT, condense_fails=True)
    lore = _FakeLoreProvider(_FOUND)
    client = _client(ruleset_dir, tmp_path, llm, lore)

    response = _ability(client, {"lore": "condensed"})

    assert response.status_code == 200
    assert _SENTINEL in llm.suggest_calls[0]["user"]
    # Provenance names what actually ran, not what was asked for.
    assert response.json()["lore"]["mode"] == "full"


def test_condense_model_env_picks_its_own_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cheaper condenser is an env var away, and unset reuses the caller's Port.

    Unset is the case that matters most for the tests above: it keeps a single
    injected mock counting every call a suggestion makes.
    """
    caller = _FakeProvider(_ABILITY_RESULT)
    assert llmmod.condense_provider(caller) is caller

    monkeypatch.setenv("LLM_CONDENSE_MODEL", "anthropic/claude-haiku-4-5")
    picked = llmmod.condense_provider(caller)
    assert picked is not caller
    assert picked.model == "anthropic/claude-haiku-4-5"


def test_condensed_miss_skips_the_extra_call(ruleset_dir: Path, tmp_path: Path) -> None:
    """Nothing was found, so there is nothing to condense — no wasted call."""
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FakeLoreProvider(loremod.LoreResult(found=False, base_species="goodra"))
    client = _client(ruleset_dir, tmp_path, llm, lore)

    _ability(client, {"lore": "condensed"})

    assert len(llm.calls) == 1


# --------------------------------------------------------------------------- #
# ac7 — provenance in every response
# --------------------------------------------------------------------------- #


def test_provenance_reports_mode_found_sources_and_chars(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    llm = _FakeProvider(_ABILITY_RESULT)
    lore = _FakeLoreProvider(_FOUND)
    client = _client(ruleset_dir, tmp_path, llm, lore)

    provenance = _ability(client, {"lore": "full"}).json()["lore"]

    assert provenance["mode"] == "full"
    assert provenance["found"] is True
    assert provenance["sources"] == list(_FOUND.sources)
    # chars is the injected block's real size, which is what makes a
    # full-vs-condensed comparison meaningful a week later.
    block = lore_text.render_lore(
        found=True,
        genus=_FOUND.genus,
        dex_entries=_FOUND.dex_entries,
        origin=_FOUND.origin,
        name_origin=_FOUND.name_origin,
        requested_id="goodra",
        base_species=_FOUND.base_species,
    )
    assert provenance["chars"] == len(block)
    assert block in llm.calls[0]["user"]
    # base_species is absent when it matched the request — no field pretending a
    # fallback happened.
    assert "base_species" not in provenance


def test_off_provenance_carries_only_the_mode(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path, _FakeProvider(_ABILITY_RESULT), _FakeLoreProvider(_FOUND))

    assert _ability(client, {"lore": "off"}).json()["lore"] == {"mode": "off"}


# --------------------------------------------------------------------------- #
# ac8 — the ledger records what ran
# --------------------------------------------------------------------------- #


def test_lore_on_suggest_appends_one_ledger_entry(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path, _FakeProvider(_ABILITY_RESULT), _FakeLoreProvider(_FOUND))

    body = _ability(client, {"lore": "full"}).json()

    entries = ledgermod.read(ruleset_dir, kind="suggest")
    assert len(entries) == 1
    assert entries[0]["chrooked_id"] == "goodra"
    assert entries[0]["capability"] == "ability"
    assert entries[0]["lore"] == body["lore"]
    assert entries[0]["ts"]


def test_lore_options_ledgers_its_own_capability(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path, _FakeProvider(_OPTIONS_RESULT), _FakeLoreProvider(_FOUND))

    _options(client, {"lore": "full"})

    entries = ledgermod.read(ruleset_dir, kind="suggest")
    assert [e["capability"] for e in entries] == ["lore-options"]


def test_lore_off_suggest_ledgers_nothing(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path, _FakeProvider(_ABILITY_RESULT), _FakeLoreProvider(_FOUND))

    _ability(client)

    assert ledgermod.read(ruleset_dir, kind="suggest") == []


# --------------------------------------------------------------------------- #
# Prompt ORDER. Found by driving the live app, not by any test here: with the
# lore block appended LAST, the first real Glalie call came back degenerate —
# all three ability slots echoed back unchanged, each "rationale" just the
# ability's own name. Both modes did it, the 1.2k condensed block as readily as
# the 3k raw one, so it was recency and not length: the prompt ended in a page
# of encyclopedia prose instead of the task. Moving lore above the constraints
# and the steer restored full reasoning immediately.
#
# The ordering is therefore load-bearing, and these pin it.
# --------------------------------------------------------------------------- #


def test_ability_context_puts_lore_before_the_steer() -> None:
    from chrooked_pokedex.web.suggest import _build_user_context

    context = _build_user_context(
        {"chrooked_id": "glalie", "name": "Glalie", "abilities": {}},
        "lean into the trapper role",
        ["primary"],
        "Researched lore (read this; do not contradict it):\nCategory: Face Pokémon",
    )
    lore_at = context.index("Researched lore")
    assert lore_at < context.index("Locked slots")
    assert lore_at < context.index("Direction from the user")


def test_typing_context_puts_lore_before_the_steer() -> None:
    from chrooked_pokedex.web.suggest import _build_typing_user_context

    context = _build_typing_user_context(
        {"chrooked_id": "glalie", "name": "Glalie"},
        "lean into the trapper role",
        "Researched lore (read this; do not contradict it):\nCategory: Face Pokémon",
    )
    assert context.index("Researched lore") < context.index("Direction from the user")


def test_an_empty_lore_block_appends_nothing_anywhere() -> None:
    # The inertness guarantee, at the assembly level rather than over HTTP.
    from chrooked_pokedex.web.suggest import _build_user_context

    entry = {"chrooked_id": "glalie", "name": "Glalie", "abilities": {}}
    assert _build_user_context(entry, "steer", None, "") == _build_user_context(
        entry, "steer", None
    )
