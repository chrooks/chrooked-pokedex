"""The lore Port: fetch a species' real published lore, so the model reads
instead of recalling.

Why this exists: the suggest capabilities ask a language model to reason from a
creature's identity — its dex flavor, its name's origin, what it was designed
after. Given no sources, the model answers from training recall, and on
2026-08-12 it justified a Glalie ability with "its name derived from *glace*
(French: ice)". The real etymology is glacier + goalie, coined because the
creature looks like a goalie mask. The suggestion rested on an invented fact.

The design is retrieval, not agency: fetch first, inject the text as context, and
keep the suggestion itself a single bounded model call. The alternative — handing
the model search tools and letting it loop — would be slower, costlier,
non-deterministic, and would rewrite every capability's prompt path.

Two sources, because neither alone is enough:

- **PokeAPI** (``pokeapi.co``) — Pokedex flavor text and the genus line, as clean
  JSON. Carries no etymology, which is exactly what got fabricated.
- **Bulbapedia** (MediaWiki API) — the ``Origin`` and ``Name origin`` sections,
  as wikitext. This is where the goalie-mask fact actually lives.

Shape mirrors :mod:`llm.py` deliberately, so the two read alike: a ``Protocol``
named :class:`LoreProvider` is the Port, :class:`HttpLoreProvider` is the real
adapter, and tests substitute a fake. Nothing here decides *whether* to fetch;
that is the caller's per-request choice, and the default is off.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Protocol, runtime_checkable

from .lore_text import clean_wikitext, fallback_base_id, pokeapi_lore

POKEAPI_BASE = "https://pokeapi.co/api/v2"
BULBAPEDIA_API = "https://bulbapedia.bulbagarden.net/w/api.php"

# Bulbapedia's API expects a descriptive agent. Identifying the tool is ordinary
# courtesy for a volunteer-run wiki and makes our traffic legible in their logs.
USER_AGENT = "chrooked-pokedex/0.1 (personal Pokemon ruleset tool; local single-user)"

# Section titles worth pulling, in the order they are injected. Matched
# case-insensitively against the page's own section list — indices are per-page
# and meaningless across pages, so they are never hardcoded.
WANTED_SECTIONS = ("Origin", "Name origin")

DEFAULT_TIMEOUT = 20.0

# Cache lives outside the Ruleset: it is fetched third-party text, not authored
# canon, and committing encyclopedia prose into the repo buys nothing.
DEFAULT_CACHE_DIR = Path(".cache/lore")


class LoreError(Exception):
    """A recoverable lore-fetch failure the caller degrades on rather than dies on.

    Covers an unreachable network or an upstream 5xx. A species that simply has
    no page is NOT this — that is an ordinary ``LoreResult(found=False)``, because
    bespoke species are a normal case in this Ruleset.
    """


@dataclass(frozen=True)
class LoreResult:
    """Everything one lookup produced. Immutable, like the rest of the model layer."""

    found: bool
    genus: str = ""
    dex_entries: tuple[str, ...] = ()
    origin: str = ""
    name_origin: str = ""
    sources: tuple[str, ...] = ()
    # The id actually looked up. Differs from the request for a form
    # (`marowakalola` -> `marowak`), which the renderer turns into a label.
    base_species: str = ""

    @property
    def chars(self) -> int:
        """Total characters of lore text held, for the provenance report."""
        return (
            len(self.genus)
            + sum(len(e) for e in self.dex_entries)
            + len(self.origin)
            + len(self.name_origin)
        )


@runtime_checkable
class LoreProvider(Protocol):
    """The Port: given a species, return what published sources say about it.

    Implementations never raise for a missing page — they return
    ``LoreResult(found=False)``. They raise :class:`LoreError` only when the
    lookup itself failed and a retry might succeed.
    """

    def fetch(self, chrooked_id: str, species_name: str) -> LoreResult: ...


class NullLoreProvider:
    """A provider that finds nothing. The honest default when lore is off.

    Also what a caller substitutes to prove the not-found path without a network.
    """

    def fetch(self, chrooked_id: str, species_name: str) -> LoreResult:
        return LoreResult(found=False, base_species=chrooked_id)


@dataclass
class _Cache:
    """A dumb on-disk cache. Dex text does not change; entries never expire.

    To refresh one species, delete its file. Kept deliberately simple — an
    invalidation policy would be complexity in service of an event that does not
    happen.
    """

    directory: Path = field(default_factory=lambda: DEFAULT_CACHE_DIR)

    def read(self, key: str) -> Optional[LoreResult]:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return None  # a corrupt cache entry is a miss, never a crash
        payload = raw.get("result", {})
        try:
            return LoreResult(
                found=bool(payload["found"]),
                genus=payload.get("genus", ""),
                dex_entries=tuple(payload.get("dex_entries") or ()),
                origin=payload.get("origin", ""),
                name_origin=payload.get("name_origin", ""),
                sources=tuple(payload.get("sources") or ()),
                base_species=payload.get("base_species", ""),
            )
        except KeyError:
            return None

    def write(self, key: str, result: LoreResult) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{key}.json"
            path.write_text(
                json.dumps(
                    {"fetched_at": time.time(), "result": asdict(result)},
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass  # a cache that cannot be written must not fail the lookup


class HttpLoreProvider:
    """The real adapter. Reads PokeAPI and Bulbapedia, caches the result.

    ``known_species`` is the set of base-species ids from the snapshot, used to
    map a form id back to the base PokeAPI recognizes. Pass it in rather than
    hardcoding form suffixes, so the mapping tracks the real dex.
    """

    def __init__(
        self,
        *,
        known_species: Iterable[str] = (),
        cache_dir: Path | None = None,
        client: Any = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.known_species = {s.strip().lower() for s in known_species}
        self._cache = _Cache(Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR)
        self._client = client
        self._timeout = timeout

    # -- HTTP ------------------------------------------------------------- #

    def _get_json(self, url: str, params: dict[str, str]) -> Optional[dict[str, Any]]:
        """One GET returning parsed JSON, ``None`` on a 404, raising on worse.

        A 404 is a legitimate answer here ("no such page"), so it is not an
        error. Anything else that fails is a :class:`LoreError` the caller
        degrades on.
        """
        client = self._client
        if client is None:
            try:
                import httpx
            except ImportError as exc:  # pragma: no cover - install-time problem
                raise LoreError(
                    "httpx is required for lore lookup; install the 'web' extra."
                ) from exc
            client = httpx.Client(timeout=self._timeout)
            close_after = True
        else:
            close_after = False
        try:
            response = client.get(url, params=params, headers={"User-Agent": USER_AGENT})
            if response.status_code == 404:
                return None
            if response.status_code >= 400:
                raise LoreError(f"{url} returned HTTP {response.status_code}")
            return response.json()
        except LoreError:
            raise
        except Exception as exc:  # network down, DNS, malformed JSON
            raise LoreError(f"lore fetch failed for {url}: {exc}") from exc
        finally:
            if close_after:
                client.close()

    # -- Sources ----------------------------------------------------------- #

    def _pokeapi(self, species_id: str) -> tuple[str, tuple[str, ...], str, str]:
        """Dex text for one id, falling back to its base species on a 404.

        The 404 is the only honest signal that a form has no page of its own.
        Guessing up front does not work here: canon regional forms like
        ``marowakalola`` ARE their own species in the base snapshot, so "is this
        a known species" says nothing about whether PokeAPI holds it — and it
        does not. Try the id, then try the base.

        Returns ``(genus, entries, url, resolved_id)``.
        """
        for candidate in self._candidates(species_id):
            url = f"{POKEAPI_BASE}/pokemon-species/{candidate}"
            payload = self._get_json(url, {})
            if payload is None:
                continue
            genus, entries = pokeapi_lore(payload)
            if genus or entries:
                return genus, entries, url, candidate
        return "", (), "", species_id

    def _candidates(self, species_id: str) -> list[str]:
        """The id itself, then its longest known base species if it has one."""
        base = fallback_base_id(species_id, self.known_species)
        return [species_id, base] if base else [species_id]

    def _bulbapedia(self, species_name: str) -> tuple[str, str, str]:
        """The Origin and Name origin sections as plain prose, plus the page URL.

        Two requests: the section list first, because section indices are
        per-page — Glalie's ``Origin`` is 46 and ``Name origin`` is 47, and those
        numbers mean nothing on any other page — then one fetch per wanted
        section, matched by title.
        """
        page = f"{species_name} (Pokémon)"
        listing = self._get_json(
            BULBAPEDIA_API,
            {"action": "parse", "page": page, "prop": "sections", "format": "json"},
        )
        if not listing or "parse" not in listing:
            return "", "", ""

        wanted = {title.casefold(): "" for title in WANTED_SECTIONS}
        index_by_title: dict[str, str] = {}
        for section in listing["parse"].get("sections", []):
            title = str(section.get("line", "")).strip().casefold()
            if title in wanted and title not in index_by_title:
                index_by_title[title] = str(section.get("index", ""))

        for title, index in index_by_title.items():
            if not index:
                continue
            payload = self._get_json(
                BULBAPEDIA_API,
                {
                    "action": "parse",
                    "page": page,
                    "section": index,
                    "prop": "wikitext",
                    "format": "json",
                },
            )
            if not payload:
                continue
            raw = (payload.get("parse", {}).get("wikitext", {}) or {}).get("*", "")
            wanted[title] = clean_wikitext(raw)

        page_url = (
            "https://bulbapedia.bulbagarden.net/wiki/"
            + page.replace(" ", "_")
        )
        origin = wanted.get("origin", "")
        name_origin = wanted.get("name origin", "")
        # MediaWiki returns a section WITH its subsections, and "Name origin" is
        # a child of "Origin" — so the etymology arrives twice and pays for the
        # character budget twice. Keep it under its own heading only.
        if name_origin and name_origin in origin:
            origin = origin.replace(name_origin, "").strip()
        return origin, name_origin, (page_url if (origin or name_origin) else "")

    # -- Port -------------------------------------------------------------- #

    def fetch(self, chrooked_id: str, species_name: str) -> LoreResult:
        """Look one species up, cache first. Never raises for a missing page."""
        cached = self._cache.read(chrooked_id)
        if cached is not None:
            return cached

        genus, entries, pokeapi_url, resolved = self._pokeapi(chrooked_id)
        origin, name_origin, bulba_url = self._bulbapedia(species_name)

        sources = tuple(u for u in (pokeapi_url, bulba_url) if u)
        result = LoreResult(
            found=bool(genus or entries or origin or name_origin),
            genus=genus,
            dex_entries=entries,
            origin=origin,
            name_origin=name_origin,
            sources=sources,
            # What the dex text actually describes. Equal to the request when the
            # species had its own page; the base when we fell back to one.
            base_species=resolved,
        )
        # Keyed by the REQUESTED id, not the resolved one: two forms of the same
        # base can render different labels, and caching under the base would make
        # the second form inherit the first's label.
        self._cache.write(chrooked_id, result)
        return result
