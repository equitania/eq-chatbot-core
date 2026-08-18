"""Tests for the shared streamed tool-call fold."""

from unittest.mock import MagicMock

import pytest

from eq_chatbot_core.providers.stream_accumulator import ToolCallAccumulator

pytestmark = pytest.mark.unit


def _sdk_delta(index=0, call_id=None, name=None, arguments=None):
    """Mimic the typed delta object the openai/anthropic SDKs yield."""
    tc = MagicMock()
    tc.index = index
    tc.id = call_id
    if name is None and arguments is None:
        tc.function = None
    else:
        tc.function = MagicMock()
        tc.function.name = name
        tc.function.arguments = arguments
    return tc


class TestEmptyState:
    def test_result_is_none_before_anything_is_added(self):
        assert ToolCallAccumulator().result() is None

    def test_falsy_input_is_ignored(self):
        acc = ToolCallAccumulator()
        acc.add(None)
        acc.add([])
        assert acc.result() is None

    def test_bool_reflects_emptiness(self):
        acc = ToolCallAccumulator()
        assert not acc
        acc.add([{"index": 0, "id": "c1"}])
        assert acc


class TestDictDeltas:
    """The raw-SSE providers (local, mammouth, openrouter) parse deltas as dicts."""

    def test_fragments_are_concatenated(self):
        acc = ToolCallAccumulator()
        acc.add([{"index": 0, "id": "call_1", "function": {"name": "get_", "arguments": '{"city'}}])
        acc.add([{"index": 0, "function": {"name": "time", "arguments": '":"NYC"}'}}])

        assert acc.result() == [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_time", "arguments": '{"city":"NYC"}'},
            }
        ]

    def test_missing_index_defaults_to_zero(self):
        """Some gateways omit index for a single tool call."""
        acc = ToolCallAccumulator()
        acc.add([{"id": "c1", "function": {"name": "f", "arguments": "{}"}}])

        assert acc.result()[0]["function"]["name"] == "f"

    def test_id_arriving_late_is_still_captured(self):
        acc = ToolCallAccumulator()
        acc.add([{"index": 0, "function": {"name": "f"}}])
        acc.add([{"index": 0, "id": "late-id"}])

        assert acc.result()[0]["id"] == "late-id"

    def test_id_is_not_overwritten_by_a_later_empty_one(self):
        acc = ToolCallAccumulator()
        acc.add([{"index": 0, "id": "c1"}])
        acc.add([{"index": 0, "id": None, "function": {"arguments": "{}"}}])

        assert acc.result()[0]["id"] == "c1"

    def test_missing_id_yields_empty_string_not_none(self):
        acc = ToolCallAccumulator()
        acc.add([{"index": 0, "function": {"name": "f"}}])

        assert acc.result()[0]["id"] == ""

    def test_type_is_always_function(self):
        acc = ToolCallAccumulator()
        acc.add([{"index": 0, "id": "c1"}])

        assert acc.result()[0]["type"] == "function"


class TestOrdering:
    def test_results_are_ordered_by_index_not_arrival(self):
        acc = ToolCallAccumulator()
        acc.add([{"index": 2, "id": "third"}])
        acc.add([{"index": 0, "id": "first"}])
        acc.add([{"index": 1, "id": "second"}])

        assert [c["id"] for c in acc.result()] == ["first", "second", "third"]

    def test_parallel_calls_accumulate_independently(self):
        acc = ToolCallAccumulator()
        acc.add(
            [
                {"index": 0, "id": "a", "function": {"name": "alpha", "arguments": "{"}},
                {"index": 1, "id": "b", "function": {"name": "beta", "arguments": "["}},
            ]
        )
        acc.add(
            [
                {"index": 0, "function": {"arguments": "}"}},
                {"index": 1, "function": {"arguments": "]"}},
            ]
        )

        result = acc.result()
        assert result[0]["function"] == {"name": "alpha", "arguments": "{}"}
        assert result[1]["function"] == {"name": "beta", "arguments": "[]"}


class TestSdkObjectDeltas:
    """The SDK-backed providers (openai, openai_compatible, langdock) yield objects."""

    def test_fragments_are_concatenated(self):
        acc = ToolCallAccumulator()
        acc.add([_sdk_delta(0, "call_1", "get_", '{"a')])
        acc.add([_sdk_delta(0, None, "time", '":1}')])

        assert acc.result() == [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_time", "arguments": '{"a":1}'},
            }
        ]

    def test_delta_without_function_is_tolerated(self):
        acc = ToolCallAccumulator()
        acc.add([_sdk_delta(0, "call_1")])

        assert acc.result() == [{"id": "call_1", "type": "function", "function": {"name": "", "arguments": ""}}]

    def test_object_and_dict_deltas_produce_the_same_shape(self):
        from_objects = ToolCallAccumulator()
        from_objects.add([_sdk_delta(0, "c1", "fn", "{}")])

        from_dicts = ToolCallAccumulator()
        from_dicts.add([{"index": 0, "id": "c1", "function": {"name": "fn", "arguments": "{}"}}])

        assert from_objects.result() == from_dicts.result()
