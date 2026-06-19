"""Issue #6 Phase A — the LiteLLM Adapter's pure helpers (no network, no key).

These cover the Adapter's seams that don't need `litellm`: the cache-friendly
message shape (a `cache_control` breakpoint on the stable context block), the
forced-schema tool wrapper, the structured-output parser, the model-string
routing, and the missing-key recoverable error. The actual `litellm.completion`
call is never exercised here — the endpoint tests mock the whole Port — so the
suite stays keyless and offline.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chrooked_pokedex.web import llm as llmmod


def test_messages_put_cache_control_on_stable_context() -> None:
    messages = llmmod.LiteLlmProvider._build_messages(
        "RUBRIC", "BIG STABLE POOL", "fresh species delta"
    )
    system = messages[0]
    assert system["role"] == "system"
    # The rubric block is uncached; the large pool block carries the breakpoint.
    assert system["content"][0] == {"type": "text", "text": "RUBRIC"}
    assert system["content"][1]["text"] == "BIG STABLE POOL"
    assert system["content"][1]["cache_control"] == {"type": "ephemeral"}
    # The per-item delta is the fresh user turn, after the cached prefix.
    assert messages[1] == {"role": "user", "content": "fresh species delta"}


def test_schema_tool_forces_named_function() -> None:
    schema = {"type": "object", "properties": {}}
    tool = llmmod.LiteLlmProvider._build_schema_tool(schema)
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "emit_proposal"
    assert tool["function"]["parameters"] is schema


def test_model_string_prepends_provider_when_unqualified() -> None:
    provider = llmmod.LiteLlmProvider(provider="anthropic", model="claude-sonnet-4-6")
    assert provider._model_string() == "anthropic/claude-sonnet-4-6"


def test_model_string_passes_through_qualified() -> None:
    provider = llmmod.LiteLlmProvider(provider="anthropic", model="openai/gpt-4o")
    assert provider._model_string() == "openai/gpt-4o"


def test_default_model_is_sonnet() -> None:
    assert llmmod.DEFAULT_MODEL == "claude-sonnet-4-6"


def test_missing_key_raises_recoverable_error(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = llmmod.LiteLlmProvider(provider="anthropic", model="claude-sonnet-4-6")
    with pytest.raises(llmmod.LlmError) as excinfo:
        provider._require_key()
    assert "ANTHROPIC_API_KEY" in str(excinfo.value)


def test_unkeyed_provider_skips_key_gate() -> None:
    # Bedrock/Ollama/HF don't gate on a single key; _require_key is a no-op.
    provider = llmmod.LiteLlmProvider(provider="ollama", model="llama3")
    provider._require_key()  # must not raise


def test_parse_tool_arguments_reads_json_string() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(arguments='{"draft": {"abilities": {}}}')
                        )
                    ]
                )
            )
        ]
    )
    assert llmmod.LiteLlmProvider._parse_tool_arguments(response) == {
        "draft": {"abilities": {}}
    }


def test_parse_tool_arguments_no_tool_call_is_llm_error() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None))]
    )
    with pytest.raises(llmmod.LlmError):
        llmmod.LiteLlmProvider._parse_tool_arguments(response)


def test_parse_tool_arguments_bad_json_is_llm_error() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(function=SimpleNamespace(arguments="not json"))
                    ]
                )
            )
        ]
    )
    with pytest.raises(llmmod.LlmError):
        llmmod.LiteLlmProvider._parse_tool_arguments(response)


def test_build_provider_returns_a_port() -> None:
    provider = llmmod.build_provider()
    assert isinstance(provider, llmmod.LlmProvider)
