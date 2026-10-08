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


def capability_supported(capabilities: Any, name: str) -> bool | None:
    """``capabilities.<name>.supported`` from the Models API, or ``None`` if not reported."""
    value = getattr(getattr(capabilities, name, None), "supported", None)
    return value if isinstance(value, bool) else None


def list_anthropic_models(client: Any, base_url: str, provider: str, **extra: Any) -> list[dict[str, Any]]:
    """The Models API's list as ``list_models()`` entries, newest first.

    Limits and capabilities come from the API only; whatever it does not report
    is ``None``. ``extra`` keys (e.g. LangDock's backend and region) are added to
    every entry.
    """
    entries = []
    # Iterating the page (not `.data`) follows the API's pagination past the first 100.
    for model in client.models.list(limit=100):
        capabilities = getattr(model, "capabilities", None)
        entries.append(
            {
                "id": model.id,
                "name": getattr(model, "display_name", None) or model.id,
                "created": getattr(model, "created_at", None),
                "provider": provider,
                **extra,
                **param_learning.model_metadata(
                    base_url,
                    model.id,
                    context_length=getattr(model, "max_input_tokens", None),
                    max_output_tokens=getattr(model, "max_tokens", None),
                    supports_vision=capability_supported(capabilities, "image_input"),
                    supports_reasoning=capability_supported(capabilities, "thinking"),
                ),
            }
        )
    entries.sort(key=lambda m: m.get("created") or "", reverse=True)
    return entries
