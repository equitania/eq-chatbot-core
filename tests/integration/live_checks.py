"""Assertions shared by the per-provider live tests (real API calls)."""

from typing import Any

WEATHER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}
# Generous: reasoning models spend part of the budget before answering.
_BUDGET = 512


def check_chat(provider: Any, model: str) -> None:
    r = provider.chat_completion([{"role": "user", "content": "Say 'test' only."}], model=model, max_tokens=_BUDGET)
    assert "test" in r.content.lower(), r.content
    assert r.input_tokens > 0 and r.output_tokens > 0


def check_stream(provider: Any, model: str) -> None:
    chunks = list(
        provider.stream_completion([{"role": "user", "content": "Say 'test' only."}], model=model, max_tokens=_BUDGET)
    )
    assert "test" in "".join(c.content for c in chunks).lower()
    assert chunks[-1].is_final


def check_tool_call(provider: Any, model: str) -> None:
    r = provider.chat_completion(
        [{"role": "user", "content": "What is the weather in Berlin? Use the tool."}],
        model=model,
        tools=[WEATHER_TOOL],
        max_tokens=_BUDGET,
    )
    assert r.tool_calls, f"no tool call; content={r.content!r}"
    assert r.tool_calls[0]["function"]["name"] == "get_weather"
    assert "berlin" in r.tool_calls[0]["function"]["arguments"].lower()
