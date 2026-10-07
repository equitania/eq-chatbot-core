"""Runtime-learned request-parameter support, per (endpoint, model).

Models differ in whether they accept ``temperature`` and whether they want the
output limit as ``max_tokens`` or ``max_completion_tokens`` — and the answer
changes between model generations faster than a hand-kept list can follow.
Instead of guessing from the model name alone, the OpenAI-compatible provider
sends what the caller asked for, recognises the provider's "unsupported
parameter" rejection, retries once with the parameter adjusted, and records the
fact here so later requests are right the first time.

The memory is process-wide (consumers such as the Odoo module build a provider
per request), thread-safe, holds two flags per key, and is never persisted.
"""

from __future__ import annotations

import re
import threading
from typing import Any

LEARNABLE: tuple[str, ...] = ("temperature", "max_tokens")

# Codes that mean "this model does not take this parameter" — as opposed to
# "invalid_value" (out of range), which must reach the caller unchanged.
_REJECTION_CODES = frozenset({"unsupported_parameter", "unsupported_value"})
_QUOTED_PARAM = re.compile(r"""['"`](temperature|max_tokens)['"`]""")

_lock = threading.Lock()
_no_temperature: set[tuple[str, str]] = set()
_completion_tokens: set[tuple[str, str]] = set()


def _key(base_url: str, model: str) -> tuple[str, str]:
    return base_url.rstrip("/"), model


def rejected_parameter(error: BaseException) -> str | None:
    """Return the learnable parameter a 400 response rejected, or ``None``.

    Structured form first: ``error.param`` names the parameter and ``code`` is an
    unsupported-* code (OpenAI). Fallback for gateways that drop ``param``: the
    message quotes the parameter name and says "unsupported"/"not supported".
    """
    if getattr(error, "status_code", None) != 400:
        return None
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        param = body.get("param")
        code = body.get("code")
        if param:
            return param if param in LEARNABLE and code in _REJECTION_CODES else None
        message = str(body.get("message") or "")
    else:
        message = str(error)
    lowered = message.lower()
    if "unsupported" not in lowered and "not supported" not in lowered:
        return None
    match = _QUOTED_PARAM.search(message)
    return match.group(1) if match else None


def adjust(params: dict[str, Any], parameter: str) -> bool:
    """Rewrite ``params`` to avoid ``parameter``. Returns False if nothing changed."""
    if parameter == "temperature" and "temperature" in params:
        del params["temperature"]
        return True
    if parameter == "max_tokens" and "max_tokens" in params:
        params["max_completion_tokens"] = params.pop("max_tokens")
        return True
    return False


def apply(base_url: str, model: str, params: dict[str, Any]) -> None:
    """Apply everything learned for (base_url, model) to ``params`` in place."""
    key = _key(base_url, model)
    with _lock:
        drop_temperature = key in _no_temperature
        rename_tokens = key in _completion_tokens
    if drop_temperature:
        adjust(params, "temperature")
    if rename_tokens:
        adjust(params, "max_tokens")


def mark_unsupported(base_url: str, model: str, parameter: str) -> None:
    key = _key(base_url, model)
    with _lock:
        if parameter == "temperature":
            _no_temperature.add(key)
        elif parameter == "max_tokens":
            _completion_tokens.add(key)


def seed_temperature_support(base_url: str, model: str, supported: bool) -> None:
    """Record temperature support reported by the provider's own model list."""
    key = _key(base_url, model)
    with _lock:
        if supported:
            _no_temperature.discard(key)
        else:
            _no_temperature.add(key)


def clear() -> None:
    with _lock:
        _no_temperature.clear()
        _completion_tokens.clear()
