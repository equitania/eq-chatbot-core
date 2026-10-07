"""Helpers shared by AnthropicProvider and LangDock's ``anthropic`` backend.

Whether a model takes ``temperature`` is learned from the Messages API's own
rejection (newer models answer "`temperature` is deprecated for this model.")
and remembered per endpoint and model in ``param_learning``. ``max_tokens`` is
mandatory in this API and is never learned here. Only ``temperature`` is
learnable: ``reasoning_effort`` is not sent on these paths.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack
from typing import Any

from eq_chatbot_core.providers import param_learning

ANTHROPIC_LEARNABLE: tuple[str, ...] = ("temperature",)


def create_message(client: Any, params: dict[str, Any], *, base_url: str, provider: str, logger: logging.Logger) -> Any:
    """``client.messages.create(**params)``, retried once without a rejected temperature."""
    return param_learning.call_with_learning(
        lambda: client.messages.create(**params),
        base_url,
        params,
        provider=provider,
        logger=logger,
        only=ANTHROPIC_LEARNABLE,
    )


def open_message_stream(
    stack: ExitStack,
    client: Any,
    params: dict[str, Any],
    *,
    base_url: str,
    provider: str,
    logger: logging.Logger,
) -> Any:
    """Enter ``client.messages.stream(**params)`` on ``stack``, with the same retry rule.

    The SDK sends the request when the stream manager is entered, before any
    event is read, so a retry never duplicates output already yielded.
    """
    return param_learning.call_with_learning(
        lambda: stack.enter_context(client.messages.stream(**params)),
        base_url,
        params,
        provider=provider,
        logger=logger,
        only=ANTHROPIC_LEARNABLE,
    )
