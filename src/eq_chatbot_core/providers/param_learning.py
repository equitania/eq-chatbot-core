"""Runtime-learned request-parameter support, per (endpoint, model).

Models differ in whether they accept ``temperature``, whether they want the
output limit as ``max_tokens`` or ``max_completion_tokens``, and whether they
take ``reasoning_effort`` — and the answer changes between model generations
faster than any list could follow. Providers send what the caller asked for,
recognise the provider's "unsupported parameter" rejection, retry once with the
parameter adjusted, and record the fact here so later requests are right the
first time.

The memory is process-wide (consumers such as the Odoo module build a provider
per request), thread-safe, holds three flags per key, and is never persisted.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

LEARNABLE: tuple[str, ...] = ("temperature", "max_tokens", "reasoning_effort")

# Keys of the capability/constraint part of a list_models() entry. A value the
# provider does not report is None (unknown) — never a guess from the name.
METADATA_KEYS: tuple[str, ...] = (
    "supports_temperature",
    "default_temperature",
    "min_temperature",
    "max_temperature",
    "supports_reasoning",
    "supports_vision",
    "max_output_tokens",
    "default_max_tokens",
    "context_length",
)

# Codes that mean "this model does not take this parameter" — as opposed to
# "invalid_value" (out of range), which must reach the caller unchanged.
_REJECTION_CODES = frozenset({"unsupported_parameter", "unsupported_value"})
# "deprecated" is Anthropic's wording ("`temperature` is deprecated for this model.").
_REJECTION_WORDS = ("unsupported", "not supported", "deprecated")
_QUOTED_PARAM = re.compile(r"""['"`](temperature|max_tokens|reasoning_effort)['"`]""")

_lock = threading.Lock()
_MEMORY: dict[str, set[tuple[str, str]]] = {parameter: set() for parameter in LEARNABLE}


def _key(base_url: str, model: str) -> tuple[str, str]:
    return base_url.rstrip("/"), model


def rejected_parameter(error: BaseException) -> str | None:
    """Return the learnable parameter a 400 response rejected, or ``None``.

    Structured form first: ``error.param`` names the parameter and ``code`` is an
    unsupported-* code (OpenAI). Fallback for bodies without ``param`` (gateways,
    Anthropic): the message quotes the parameter name and says "unsupported",
    "not supported" or "deprecated". Anthropic wraps its error in an envelope
    (``{"type": "error", "error": {...}}``), which is unwrapped first.
    """
    if getattr(error, "status_code", None) != 400:
        return None
    body = getattr(error, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        body = body["error"]
    if isinstance(body, dict):
        param = body.get("param")
        code = body.get("code")
        if param:
            return param if param in LEARNABLE and code in _REJECTION_CODES else None
        message = str(body.get("message") or "")
    else:
        message = str(error)
    lowered = message.lower()
    if not any(word in lowered for word in _REJECTION_WORDS):
        return None
    match = _QUOTED_PARAM.search(message)
    return match.group(1) if match else None


def adjust(params: dict[str, Any], parameter: str) -> bool:
    """Rewrite ``params`` to avoid ``parameter``. Returns False if nothing changed.

    ``temperature`` is removed wherever it is — top level (OpenAI wire) or inside
    ``extra_body`` (Anthropic SDK; the caller's dict is copied, not mutated).
    ``max_tokens`` becomes ``max_completion_tokens``. ``reasoning_effort`` is removed.
    """
    if parameter == "temperature":
        if "temperature" in params:
            del params["temperature"]
            return True
        extra_body = params.get("extra_body")
        if isinstance(extra_body, dict) and "temperature" in extra_body:
            remaining = {k: v for k, v in extra_body.items() if k != "temperature"}
            if remaining:
                params["extra_body"] = remaining
            else:
                del params["extra_body"]
            return True
        return False
    if parameter == "max_tokens" and "max_tokens" in params:
        params["max_completion_tokens"] = params.pop("max_tokens")
        return True
    if parameter == "reasoning_effort" and "reasoning_effort" in params:
        del params["reasoning_effort"]
        return True
    return False


def apply(base_url: str, model: str, params: dict[str, Any], *, only: tuple[str, ...] = LEARNABLE) -> None:
    """Apply what was learned for (base_url, model) to ``params`` in place, limited to ``only``."""
    key = _key(base_url, model)
    with _lock:
        learned = [parameter for parameter in only if key in _MEMORY.get(parameter, set())]
    for parameter in learned:
        adjust(params, parameter)


def mark_unsupported(base_url: str, model: str, parameter: str) -> None:
    memory = _MEMORY.get(parameter)
    if memory is None:
        return
    with _lock:
        memory.add(_key(base_url, model))


def learn_from_rejection(
    error: BaseException,
    base_url: str,
    model: str,
    params: dict[str, Any],
    adjusted: set[str],
    *,
    provider: str,
    logger: logging.Logger,
    only: tuple[str, ...] = LEARNABLE,
) -> bool:
    """Handle one failed request. True means ``params`` was adjusted: send it again.

    At most one retry per parameter and call (``adjusted`` collects them); a
    parameter rejected again after its adjustment propagates. Logged at INFO on
    the caller's logger so each provider module reports its own retries.
    """
    parameter = rejected_parameter(error)
    if parameter is None or parameter not in only or parameter in adjusted or not adjust(params, parameter):
        return False
    adjusted.add(parameter)
    mark_unsupported(base_url, model, parameter)
    logger.info(
        "%s: model %s rejected '%s'; retrying adjusted and remembering it for this endpoint",
        provider,
        model,
        parameter,
    )
    return True


def seed_temperature_support(base_url: str, model: str, supported: bool) -> None:
    """Record temperature support reported by the provider's own model list."""
    key = _key(base_url, model)
    with _lock:
        if supported:
            _MEMORY["temperature"].discard(key)
        else:
            _MEMORY["temperature"].add(key)


def temperature_support(base_url: str, model: str) -> bool | None:
    """``False`` once a temperature rejection was learned or seeded; otherwise ``None`` (unknown)."""
    with _lock:
        return False if _key(base_url, model) in _MEMORY["temperature"] else None


def model_metadata(base_url: str, model: str, **reported: Any) -> dict[str, Any]:
    """The ``METADATA_KEYS`` part of a ``list_models()`` entry.

    ``reported`` holds what the provider's API said; every other key is ``None``.
    A learned temperature rejection makes ``supports_temperature`` ``False``
    whatever the API reported.
    """
    meta: dict[str, Any] = dict.fromkeys(METADATA_KEYS)
    meta.update(reported)
    if temperature_support(base_url, model) is False:
        meta["supports_temperature"] = False
    return meta


def clear() -> None:
    with _lock:
        for memory in _MEMORY.values():
            memory.clear()
