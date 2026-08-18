"""Shared accumulation of streamed OpenAI-style tool-call deltas.

A streamed tool call arrives in fragments: the first delta carries the id and
the function name, later ones append argument text, and the caller has to fold
them back into whole calls keyed by index. Six providers implemented that same
fold inline — SDK-object flavoured in the OpenAI/Anthropic SDK paths, dict
flavoured in the raw-SSE ones — which is why ``stream_completion`` was the
longest method in every one of them.

Only the fold is shared here. Each provider still builds its own
``tool_call_delta`` payload, because those differ on purpose (some emit a single
normalized dict per delta, others pass the raw list through) and unifying them
would change what consumers receive.
"""

from typing import Any


def _field(obj: Any, key: str) -> Any:
    """Read ``key`` from either an SDK object or a plain dict.

    Streaming deltas reach us as typed SDK objects through the openai/anthropic
    clients and as parsed JSON dicts through the raw-SSE providers.
    """
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


class ToolCallAccumulator:
    """Folds streamed tool-call deltas into complete tool calls.

    Example:
        >>> acc = ToolCallAccumulator()
        >>> acc.add([{"index": 0, "id": "call_1", "function": {"name": "get_", "arguments": '{"a'}}])
        >>> acc.add([{"index": 0, "function": {"name": "time", "arguments": '":1}'}}])
        >>> acc.result()
        [{'id': 'call_1', 'type': 'function', 'function': {'name': 'get_time', 'arguments': '{"a":1}'}}]
    """

    def __init__(self) -> None:
        self._calls: dict[int, dict[str, Any]] = {}

    def add(self, tool_calls: Any) -> None:
        """Fold one delta's ``tool_calls`` into the accumulated state.

        Args:
            tool_calls: The delta's tool-call list (SDK objects or dicts).
                Falsy values are ignored, so callers can pass the raw field.
        """
        for tc in tool_calls or ():
            index = _field(tc, "index")
            if index is None:
                # Single-tool responses from some gateways omit the index.
                index = 0

            entry = self._calls.setdefault(
                index,
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
            )

            call_id = _field(tc, "id")
            if call_id:
                entry["id"] = call_id

            function = _field(tc, "function")
            if function:
                name = _field(function, "name")
                if name:
                    entry["function"]["name"] += name
                arguments = _field(function, "arguments")
                if arguments:
                    entry["function"]["arguments"] += arguments

    def result(self) -> list[dict[str, Any]] | None:
        """Return the completed tool calls ordered by index, or None if there were none.

        None rather than an empty list: the streaming chunk types treat a missing
        ``tool_calls`` as "this response had none", and an empty list would read
        as "there were tool calls, but no data".
        """
        if not self._calls:
            return None
        return [self._calls[index] for index in sorted(self._calls)]

    def __bool__(self) -> bool:
        return bool(self._calls)
