"""The provider-agnostic LLM client — a Ports & Adapters Seam (D-D).

The app depends on an :class:`LlmProvider` **Port**, never on a vendor SDK, so
open-source users can swap the gen-AI backend by config ("USB for AI"). Concrete
Adapters are chosen at runtime from environment variables; the default Adapter
wraps `LiteLLM`, which speaks 100+ providers behind one interface — Claude /
OpenAI / Bedrock / Ollama / HuggingFace all plug in by changing ``LLM_MODEL``.

The Port's shape is the reusable contract every later capability (#7/#8/#9/#10/
#32) plugs into: each supplies a *capability prompt* (``system`` rubric +
``user`` per-item context) and a *field set* (the JSON ``schema`` of the draft),
and gets a structured, shape-valid draft back from a single bounded call. The
caller — not this module — assembles context, builds the rubric, and validates
the draft against real data; the Port only forces the model's output into the
requested shape and surfaces honest, recoverable errors.

Caching: the Port exposes a ``cached_context`` slot for the large, stable prefix
(the ability/move pool, the type chart). Each Adapter caches it however its
provider supports — Anthropic via explicit ``cache_control`` breakpoints — so the
per-item ``user`` delta stays fresh and cheap. Caching is provider-specific, so
it lives *inside* the Adapter behind the agnostic slot.

Secrets: the provider key is read from the environment only, never logged, and
never returned to the client. A missing key or an upstream API/timeout error is
raised as :class:`LlmError` (a recoverable error the endpoint surfaces as an
honest message), not an unhandled 500 traceback.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

# Defaults (D-D): Anthropic Sonnet, key from ANTHROPIC_API_KEY. Every value is
# env-overridable so the backend is swappable without a code change.
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-6"
# A single bounded call: cap output so a runaway response can't blow up cost or
# latency. The draft is small (a few slots + short rationales), so this is ample.
DEFAULT_MAX_TOKENS = 1024

# Per-provider env var holding the API key. The Adapter validates presence
# itself and raises a recoverable error — it never reads a key into a log line.
_PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
    # Bedrock / Ollama / HuggingFace authenticate differently (AWS creds, a
    # local daemon, an HF token); they're reachable via LiteLLM but aren't
    # gated on a single key here, so they're absent from this map by design.
}


class LlmError(Exception):
    """A recoverable LLM failure the endpoint surfaces as an honest message.

    Covers a missing provider key, an upstream API/timeout error, and a
    malformed structured response. Never carries the key or a raw vendor
    traceback to the client; the endpoint maps it to a clean 4xx/5xx detail.
    """


@runtime_checkable
class LlmProvider(Protocol):
    """The Port: a provider-agnostic single-call structured-proposal Surface.

    `propose` runs ONE bounded call and returns a **shape-valid** dict matching
    `schema` (forced via the provider's tool-use / JSON-schema mode), so the
    draft is structurally trustworthy even though its *content* is never
    trusted (the loader/CRUD Boundary is the real gate). Implementations are
    the swappable Adapters; tests substitute a fake that records the call.
    """

    def propose(
        self,
        *,
        system: str,
        cached_context: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """Return a shape-valid draft dict for `schema` from one bounded call.

        - ``system``: the stable role + scoring rubric (cacheable prefix head).
        - ``cached_context``: the large, stable pool/context to prompt-cache.
        - ``user``: the fresh per-item delta (this species + direction).
        - ``schema``: JSON schema the output is forced to match.
        - ``max_tokens``: hard output cap for the single call.

        Raises :class:`LlmError` on missing key, API/timeout, or unparseable
        output — never an unhandled provider exception.
        """
        ...


class LiteLlmProvider:
    """The default Adapter: LiteLLM behind the Port (D-D).

    LiteLLM is imported lazily inside `propose` so importing this module — and
    running the test suite — never requires the package or a key. Tests mock the
    Port, so CI stays keyless and offline; only a real proposal touches LiteLLM.
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider or os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER)
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)

    def _require_key(self) -> None:
        """Fail fast with a recoverable error when the provider key is absent.

        The realistic local failure is "the user never set their key". We turn
        that into an actionable :class:`LlmError` BEFORE any network call so the
        endpoint surfaces a clean message, not a vendor auth traceback. The key
        value is never read into the message.
        """
        env_name = _PROVIDER_KEY_ENV.get(self.provider)
        if env_name is None:
            # Providers without a single-key gate (Bedrock/Ollama/HF) skip this.
            return
        if not os.environ.get(env_name):
            raise LlmError(
                f"No API key for provider {self.provider!r}: set the {env_name} "
                "environment variable to enable LLM suggestions."
            )

    def _model_string(self) -> str:
        """The LiteLLM model string (``provider/model``).

        LiteLLM routes on a ``provider/model`` prefix. If the configured model
        already carries a slash (the user set a fully-qualified string), pass it
        through; otherwise prepend the configured provider.
        """
        if "/" in self.model:
            return self.model
        return f"{self.provider}/{self.model}"

    def propose(
        self,
        *,
        system: str,
        cached_context: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        self._require_key()
        try:
            import litellm  # lazy: keeps import/test paths key- and dep-free
        except ImportError as error:  # pragma: no cover - exercised via packaging
            raise LlmError(
                "The 'litellm' package is required for LLM suggestions but is "
                "not installed; install it with `pip install litellm`."
            ) from error

        messages = self._build_messages(system, cached_context, user)
        tool = self._build_schema_tool(schema)
        try:
            response = litellm.completion(
                model=self._model_string(),
                messages=messages,
                tools=[tool],
                tool_choice={
                    "type": "function",
                    "function": {"name": tool["function"]["name"]},
                },
                max_tokens=max_tokens,
            )
        except Exception as error:  # noqa: BLE001 - normalize any vendor error
            # LiteLLM raises a wide family of provider/timeout errors; all of
            # them mean "the upstream call failed" → a single honest message.
            raise LlmError(
                f"The LLM provider call failed: {type(error).__name__}."
            ) from error

        # Detect an output truncated at the token cap before attempting to
        # parse the tool-call arguments. A truncated response surfaces as a
        # misleading parse error (bad JSON / no tool-call) without this guard.
        # Only raise when finish_reason is explicitly "length" — absent or None
        # means the model stopped normally, not that it was cut off.
        try:
            finish_reason = response.choices[0].finish_reason
        except (AttributeError, IndexError, TypeError):
            finish_reason = None
        if finish_reason == "length":
            raise LlmError(
                "The LLM response was truncated at the token limit; "
                "try again or reduce scope."
            )

        return self._parse_tool_arguments(response)

    @staticmethod
    def _build_messages(
        system: str, cached_context: str, user: str
    ) -> list[dict[str, Any]]:
        """Build the cache-friendly message list: stable prefix, then fresh delta.

        The ``system`` role carries the rubric and the large, stable
        ``cached_context`` as two blocks with an Anthropic ``cache_control``
        breakpoint on the context block — LiteLLM passes ``cache_control``
        through to providers that support it (a no-op elsewhere), so the
        expensive prefix is read from cache on repeat suggests while the
        per-species ``user`` turn stays fresh.
        """
        return [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": system},
                    {
                        "type": "text",
                        "text": cached_context,
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
            },
            {"role": "user", "content": user},
        ]

    @staticmethod
    def _build_schema_tool(schema: dict[str, Any]) -> dict[str, Any]:
        """Wrap the draft schema as a forced tool so the output is shape-valid."""
        return {
            "type": "function",
            "function": {
                "name": "emit_proposal",
                "description": (
                    "Emit the proposal as a structured object matching the schema."
                ),
                "parameters": schema,
            },
        }

    @staticmethod
    def _parse_tool_arguments(response: Any) -> dict[str, Any]:
        """Pull the forced tool-call arguments out of a LiteLLM response.

        A forced tool call returns its arguments as a JSON string; parse it to
        the draft dict. Any deviation (no tool call, bad JSON) is a malformed
        response → a recoverable :class:`LlmError`, never a raw KeyError/500.
        """
        import json

        try:
            tool_calls = response.choices[0].message.tool_calls
            arguments = tool_calls[0].function.arguments
        except (AttributeError, IndexError, TypeError) as error:
            raise LlmError(
                "The LLM response did not include a structured proposal."
            ) from error
        try:
            return json.loads(arguments)
        except (ValueError, TypeError) as error:
            raise LlmError(
                "The LLM returned a proposal that could not be parsed."
            ) from error


def build_provider() -> LlmProvider:
    """Construct the configured Adapter behind the Port.

    The single place the concrete Adapter is selected. Today it always returns
    the LiteLLM Adapter (itself config-selected by ``LLM_PROVIDER``/``LLM_MODEL``);
    a future non-LiteLLM Adapter slots in here without touching any caller.
    """
    return LiteLlmProvider()
