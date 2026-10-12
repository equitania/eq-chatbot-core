"""Runtime-learned request-parameter support, per (endpoint, model).

Models differ in whether they accept ``temperature``, whether they want the
output limit as ``max_tokens`` or ``max_completion_tokens``, and whether they
take ``reasoning_effort`` — and the answer changes between model generations
faster than any list could follow. Providers send what the caller asked for,
recognise the provider's "unsupported parameter" rejection, retry once with the
parameter adjusted, and record the fact here so later requests are right the
first time.

The memory is process-wide (consumers such as the Odoo module build a provider
per request), thread-safe, holds three flags and up to two limits per key, and is never persisted.
A key is the endpoint plus a fingerprint of the API key (see ``scope()``): a
shared gateway may route one model name to different backends per virtual key.
A rejection is remembered only once the adjusted request has succeeded.

Since 4.1.0 the same memory holds numeric limits — the output limit and the
context length — that a provider *states* in a rejection ("This model supports
at most 16384 completion tokens", "max_tokens: N > 128000, which is the maximum
allowed number of output tokens", "maximum context length is 128000 tokens").
A stated limit is remembered at once: the provider named the number, no retry
has to prove it. A request whose output limit is too large is retried once,
capped to the stated value, and later requests are capped before they are sent.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

LEARNABLE: tuple[str, ...] = (
    "temperature",
    "max_tokens",
    "reasoning_effort",
    "reasoning_with_tools",
    "stream_usage",
)

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
# "deprecated" is Anthropic's wording ("`temperature` is deprecated for this model.");
# "unrecognized" is Azure's ("Unrecognized request argument supplied: reasoning_effort").
_REJECTION_WORDS = ("unsupported", "not supported", "deprecated", "unrecognized")
_QUOTED_PARAM = re.compile(r"""['"`](temperature|max_tokens|reasoning_effort)['"`]""")
# A model that reasons by default and refuses function tools while it does (seen
# on OpenAI's /chat/completions: "Function tools with reasoning_effort are not
# supported ... set reasoning_effort to 'none'"). It is refused even when no
# reasoning_effort was sent, so the fix is to send "none" — with tools only;
# without tools the model keeps reasoning. Learned as "reasoning_with_tools".
_TOOLS_NEED_NO_REASONING = re.compile(
    r"tools with reasoning_effort are not supported|set reasoning_effort to ['\"`]?none", re.IGNORECASE
)
_SUPPLIED_PARAM = re.compile(r"argument supplied:\s*(temperature|max_tokens|reasoning_effort)\b", re.IGNORECASE)
# HTTP statuses that can carry an unsupported-parameter rejection. ``None`` is an
# error event inside an SSE stream (HTTP 200 already sent; the SDK raises without
# a status). 422 is what some gateways answer instead of 400.
_REJECTION_STATUSES = frozenset({400, 422, None})

# Numeric limits a rejection can state, and the patterns that read them.
LIMIT_KEYS: tuple[str, ...] = ("max_output_tokens", "context_length")
_OUTPUT_LIMIT_PATTERNS = (
    # OpenAI: "This model supports at most 16384 completion tokens, whereas you provided ..."
    re.compile(r"supports at most (\d+) (?:completion|output) tokens", re.IGNORECASE),
    # Anthropic: "max_tokens: 10000000 > 128000, which is the maximum allowed number of output tokens"
    re.compile(r"> (\d+), which is the maximum allowed number of output tokens", re.IGNORECASE),
)
_CONTEXT_PATTERNS = (
    # OpenAI, vLLM, LiteLLM: "This model's maximum context length is 128000 tokens."
    re.compile(r"maximum context length is (\d+) tokens", re.IGNORECASE),
    # Anthropic: "prompt is too long: 210000 tokens > 200000 maximum"
    re.compile(r"prompt is too long: \d+ tokens > (\d+) maximum", re.IGNORECASE),
)
# The input side of a context rejection that blames the output limit (vLLM: "your
# request has 20 input tokens"; older OpenAI: "(100 in the messages, 9000 in the completion)").
_INPUT_TOKENS = re.compile(r"your request has (\d+) input tokens|\((\d+) in the messages", re.IGNORECASE)
# The request parameters that carry the output limit on the wire.
_OUTPUT_PARAMS: tuple[str, ...] = ("max_tokens", "max_completion_tokens")

_lock = threading.Lock()
_MEMORY: dict[str, set[tuple[str, str]]] = {parameter: set() for parameter in LEARNABLE}
_LIMITS: dict[tuple[str, str], dict[str, int]] = {}


def _key(base_url: str, model: str) -> tuple[str, str]:
    return base_url.rstrip("/"), model


def scope(base_url: str, api_key: str | None = None) -> str:
    """The memory scope for one endpoint and API key.

    Providers pass this wherever a function here takes ``base_url``. The key is
    reduced to a short SHA-256 fingerprint, so the memory never holds a secret.
    """
    base = base_url.rstrip("/")
    if not api_key:
        return base
    return f"{base}#{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"


def _error_message(body: dict[str, Any]) -> str:
    """The message of an error body, including OpenRouter's wrapped upstream text.

    OpenRouter answers "Provider returned error" and puts the upstream body, as a
    string, under ``metadata.raw``.
    """
    message = str(body.get("message") or "")
    metadata = body.get("metadata")
    if isinstance(metadata, dict) and metadata.get("raw"):
        message = f"{message} {metadata['raw']}"
    return message


def _rejection_message(error: BaseException) -> str | None:
    """The message of a 400/422/stream-event error, or ``None`` for any other error."""
    if getattr(error, "status_code", None) not in _REJECTION_STATUSES:
        return None
    body = getattr(error, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        body = body["error"]
    return _error_message(body) if isinstance(body, dict) else str(error)


def _first_number(patterns: tuple[re.Pattern[str], ...], message: str) -> int | None:
    for pattern in patterns:
        match = pattern.search(message)
        if match:
            value = int(match.group(1))
            return value if value > 0 else None
    return None


def stated_limits(error: BaseException) -> dict[str, int]:
    """The limits a rejection states, keyed by ``LIMIT_KEYS``; empty when it states none.

    Read from the message only — the numbers are not in any structured field.
    """
    message = _rejection_message(error)
    if not message:
        return {}
    limits: dict[str, int] = {}
    output = _first_number(_OUTPUT_LIMIT_PATTERNS, message)
    if output:
        limits["max_output_tokens"] = output
    context = _first_number(_CONTEXT_PATTERNS, message)
    if context:
        limits["context_length"] = context
    return limits


def allowed_output(error: BaseException) -> int | None:
    """The largest output limit the rejected request could have sent, or ``None``.

    Either the model's stated output limit, or — for a context rejection that
    names the request's input tokens — the room the context leaves for output.
    A context rejection without that number is about the input itself and
    cannot be fixed by a smaller output limit.
    """
    limits = stated_limits(error)
    if "max_output_tokens" in limits:
        return limits["max_output_tokens"]
    message = _rejection_message(error) or ""
    match = _INPUT_TOKENS.search(message)
    if "context_length" not in limits or not match:
        return None
    room = limits["context_length"] - int(match.group(1) or match.group(2))
    return room if room > 0 else None


def cap_output(params: dict[str, Any], limit: int) -> bool:
    """Lower the output-limit parameter in ``params`` to ``limit``. True if it was above."""
    capped = False
    for name in _OUTPUT_PARAMS:
        value = params.get(name)
        if isinstance(value, int) and value > limit:
            params[name] = limit
            capped = True
    return capped


def remember_limits(base_url: str, model: str, limits: dict[str, int]) -> None:
    """Record limits for (base_url, model); unknown keys and non-positive values are ignored."""
    known = {key: value for key, value in limits.items() if key in LIMIT_KEYS and isinstance(value, int) and value > 0}
    if not known:
        return
    with _lock:
        _LIMITS.setdefault(_key(base_url, model), {}).update(known)


def learned_limits(base_url: str, model: str) -> dict[str, int]:
    """The limits remembered for (base_url, model), keyed by ``LIMIT_KEYS``."""
    with _lock:
        return dict(_LIMITS.get(_key(base_url, model), {}))


def rejected_parameter(error: BaseException) -> str | None:
    """Return the learnable parameter a request rejection names, or ``None``.

    Considered: HTTP 400 and 422, and an error event inside a stream (no status).
    Structured form first: ``error.param`` names the parameter and ``code`` is an
    unsupported-* code (OpenAI). Fallback for bodies without ``param`` (gateways,
    Anthropic, OpenRouter's ``metadata.raw``): the message names the parameter —
    quoted, or after "argument supplied:" — and says "unsupported", "not
    supported", "deprecated" or "unrecognized". Anthropic wraps its error in an
    envelope (``{"type": "error", "error": {...}}``), which is unwrapped first.
    """
    if getattr(error, "status_code", None) not in _REJECTION_STATUSES:
        return None
    body = getattr(error, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        body = body["error"]
    if _TOOLS_NEED_NO_REASONING.search(_error_message(body) if isinstance(body, dict) else str(error)):
        return "reasoning_with_tools"
    if isinstance(body, dict):
        param = body.get("param")
        code = body.get("code")
        if param:
            # For reasoning_effort, "unsupported_value" refuses one value (e.g. "none"),
            # not the parameter: learning it would silently drop every later setting.
            if param == "reasoning_effort" and code != "unsupported_parameter":
                return None
            return param if param in LEARNABLE and code in _REJECTION_CODES else None
        message = _error_message(body)
    else:
        message = str(error)
    lowered = message.lower()
    if not any(word in lowered for word in _REJECTION_WORDS):
        return None
    match = _QUOTED_PARAM.search(message) or _SUPPLIED_PARAM.search(message)
    if not match:
        return None
    # Same rule as the structured branch: one refused reasoning_effort *value* is not
    # the parameter being unsupported.
    if match.group(1) == "reasoning_effort" and "value" in lowered:
        return None
    return match.group(1)


def adjust(params: dict[str, Any], parameter: str) -> bool:
    """Rewrite ``params`` to avoid ``parameter``. Returns False if nothing changed.

    ``temperature`` is removed wherever it is — top level (OpenAI wire) or inside
    ``extra_body`` (Anthropic SDK; the caller's dict is copied, not mutated).
    ``max_tokens`` becomes ``max_completion_tokens``. ``reasoning_effort`` is removed.
    ``reasoning_with_tools`` sets ``reasoning_effort`` to ``"none"``, and only in a
    request that carries tools. ``stream_usage`` removes ``stream_options`` (servers
    that refuse to report token usage in a stream).
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
    if parameter == "reasoning_with_tools" and params.get("tools") and params.get("reasoning_effort") != "none":
        params["reasoning_effort"] = "none"
        return True
    if parameter == "stream_usage" and "stream_options" in params:
        del params["stream_options"]
        return True
    return False


def apply(base_url: str, model: str, params: dict[str, Any], *, only: tuple[str, ...] = LEARNABLE) -> None:
    """Apply what was learned for (base_url, model) to ``params`` in place, limited to ``only``."""
    key = _key(base_url, model)
    with _lock:
        learned = [parameter for parameter in only if key in _MEMORY.get(parameter, set())]
    for parameter in learned:
        adjust(params, parameter)


def learned_adjustments(base_url: str, model: str) -> list[str]:
    """The adjustments learned for (base_url, model), in ``LEARNABLE`` order.

    A consumer persists this list (e.g. after ``check_model``) and hands it back
    with ``seed_adjustments`` after a restart, so the first request is right.
    """
    key = _key(base_url, model)
    with _lock:
        return [parameter for parameter in LEARNABLE if key in _MEMORY[parameter]]


def seed_adjustments(base_url: str, model: str, adjustments: list[str] | tuple[str, ...]) -> None:
    """Restore adjustments persisted from ``learned_adjustments``; unknown names are ignored."""
    for parameter in adjustments:
        mark_unsupported(base_url, model, parameter)


def forget_adjustments(base_url: str, model: str) -> None:
    """Forget the adjustments learned for (base_url, model); limits are kept.

    A re-check starts from the plain request, so a model the provider has
    changed is noticed instead of being masked by an old adjustment.
    """
    key = _key(base_url, model)
    with _lock:
        for memory in _MEMORY.values():
            memory.discard(key)


def is_rejection(error: BaseException) -> bool:
    """True when ``error`` is the provider refusing the request as sent.

    HTTP 400/422, or an error event inside a stream (no status, but a body).
    Authentication, rate limits, server errors and network failures are not
    rejections: nothing about the request can be learned from them. A
    ``ProviderError`` is judged together with the SDK error it was raised from.
    """
    current: BaseException | None = error
    while current is not None:
        status = getattr(current, "status_code", None)
        body = getattr(current, "body", None)
        if status in (400, 422) or (status is None and body is not None):
            return not _is_transient(current, body)
        if status is not None:
            return False
        current = current.__cause__
    return False


# Words of errors that say nothing about the request: overload, rate limits,
# timeouts, and a conversation too long for the model (fixed by shortening it,
# not by changing parameters). Gateways relay them as stream error events.
_TRANSIENT_WORDS = (
    "overloaded",
    "rate limit",
    "rate_limit",
    "timeout",
    "timed out",
    "temporarily",
    "try again",
    "context length",
    "context_length",
    "maximum context",
    "prompt is too long",
)


def _is_transient(error: BaseException, body: Any) -> bool:
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        body = body["error"]
    if isinstance(body, dict):
        code = body.get("code")
        if isinstance(code, int) and (code == 429 or code >= 500):
            return True
        kind = str(body.get("type") or "")
        if kind in ("overloaded_error", "rate_limit_error", "api_error"):
            return True
        message = _error_message(body) or str(error)
    else:
        message = str(error)
    lowered = message.lower()
    return any(word in lowered for word in _TRANSIENT_WORDS)


# --- exploring ---------------------------------------------------------------------
#
# A rejection the rules above do not recognise used to reach the caller: every new
# wording a provider invents needed a code change. While ``exploring()`` is active
# (``check_model`` sets it for its small check requests, never for a conversation),
# such a rejection starts a bounded search instead: the unchanged request once more
# (a gateway may have routed it to a bad upstream), then each candidate adjustment
# alone. The first that is accepted is remembered like a recognised rejection.
#
# Candidates the error text names come first. Without a name only the harmless ones
# are tried: dropping temperature or stream usage, and switching reasoning off for a
# request with tools. Renaming max_tokens or dropping a configured reasoning_effort
# needs the name: a gateway that ignores an unknown parameter would otherwise lose
# the output limit or the setting for good.

_EXPLORING: ContextVar[bool] = ContextVar("eq_chatbot_core_exploring", default=False)

_CANDIDATE_WORDS: dict[str, tuple[str, ...]] = {
    "reasoning_with_tools": ("reasoning",),
    "temperature": ("temperature",),
    "max_tokens": ("max_tokens", "max_completion_tokens"),
    "reasoning_effort": ("reasoning_effort",),
    "stream_usage": ("stream_options", "include_usage"),
}
_UNNAMED_CANDIDATES: tuple[str, ...] = ("reasoning_with_tools", "temperature", "stream_usage")


@contextmanager
def exploring() -> Iterator[None]:
    """Explore unrecognised rejections in this context (see the section comment)."""
    token = _EXPLORING.set(True)
    try:
        yield
    finally:
        _EXPLORING.reset(token)


def is_exploring() -> bool:
    return _EXPLORING.get()


def _candidates(error: BaseException, params: dict[str, Any], only: tuple[str, ...]) -> list[str]:
    message = _rejection_message(error)
    if message is None and error.__cause__ is not None:
        message = _rejection_message(error.__cause__)
    lowered = (message or str(error)).lower()
    named = [c for c, words in _CANDIDATE_WORDS.items() if any(w in lowered for w in words)]
    if "reasoning_with_tools" in named and "tool" not in lowered:
        named.remove("reasoning_with_tools")
    ordered = named + [c for c in _UNNAMED_CANDIDATES if c not in named]
    return [c for c in ordered if c in only and adjust(dict(params), c)]


_NOT_FOUND = object()


def _explore(
    send: Callable[[], Any],
    params: dict[str, Any],
    error: BaseException,
    adjusted: set[str],
    *,
    model: str,
    provider: str,
    logger: logging.Logger,
    only: tuple[str, ...],
) -> Any:
    """The search behind ``exploring()``. Returns ``send()``'s result, or ``_NOT_FOUND``.

    Raises at once on an error that is not a rejection (authentication, rate
    limit, network): nothing can be learned from it, and every further request
    would cost the same.
    """
    try:
        return send()  # the unchanged request once more: was it a fluke?
    except Exception as again:
        if not is_rejection(again):
            raise
    original = dict(params)
    for candidate in _candidates(error, original, only):
        trial = dict(original)
        adjust(trial, candidate)
        params.clear()
        params.update(trial)
        try:
            result = send()
        except Exception as refused:
            if not is_rejection(refused):
                params.clear()
                params.update(original)
                raise
            continue
        adjusted.add(candidate)
        logger.info("%s: model %s accepted the request with '%s' adjusted", provider, model, candidate)
        return result
    params.clear()
    params.update(original)
    return _NOT_FOUND


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
    parameter rejected again after its adjustment propagates. Nothing is
    remembered here — ``call_with_learning`` marks ``adjusted`` only once the
    adjusted request succeeded, so a retry that fails for another reason (401,
    5xx, timeout) teaches nothing. Logged at INFO on the caller's logger so each
    provider module reports its own retries.
    """
    parameter = rejected_parameter(error)
    if parameter is None or parameter not in only or parameter in adjusted or not adjust(params, parameter):
        return False
    adjusted.add(parameter)
    logger.info(
        "%s: model %s rejected '%s'; retrying adjusted",
        provider,
        model,
        parameter,
    )
    return True


def _cap_to_stated_limit(
    error: BaseException,
    base_url: str,
    model: str,
    params: dict[str, Any],
    *,
    provider: str,
    logger: logging.Logger,
    cap: bool,
) -> bool:
    """Remember the limits ``error`` states; True if ``params`` was capped and should be resent."""
    limits = stated_limits(error)
    if limits:
        remember_limits(base_url, model, limits)
        logger.info(
            "%s: model %s states %s; remembered for this endpoint",
            provider,
            model,
            ", ".join(f"{key}={value}" for key, value in sorted(limits.items())),
        )
    allowed = allowed_output(error) if cap else None
    if not allowed or not cap_output(params, allowed):
        return False
    logger.info("%s: model %s rejected the output limit; retrying with %s", provider, model, allowed)
    return True


def call_with_learning(
    send: Callable[[], Any],
    base_url: str,
    params: dict[str, Any],
    *,
    provider: str,
    logger: logging.Logger,
    only: tuple[str, ...] = LEARNABLE,
    cap: bool = True,
) -> Any:
    """Apply what is learned to ``params``, then ``send()``; on a recognised rejection adjust and resend.

    ``send`` must read ``params`` when it is called (it is the one retry-and-learn
    loop, shared by every provider). Anything else, or a second rejection of the
    same parameter, propagates. The adjustments are remembered for
    (``base_url``, model) only after ``send()`` returned.

    Limits a rejection states are remembered at once. With ``cap`` (the default)
    the output limit is lowered to a remembered limit before sending, and a
    request rejected for its output limit is resent once, capped. ``cap=False``
    is for ``probe_output_limit``, whose oversized request must reach the provider.
    """
    model = params["model"]
    apply(base_url, model, params, only=only)
    if cap:
        known = learned_limits(base_url, model).get("max_output_tokens")
        if known and cap_output(params, known):
            logger.debug("%s: output limit capped to %s for model %s", provider, known, model)
    adjusted: set[str] = set()
    capped = False
    explored = False
    while True:
        try:
            result = send()
        except Exception as error:
            if learn_from_rejection(
                error, base_url, model, params, adjusted, provider=provider, logger=logger, only=only
            ):
                continue
            if not capped and _cap_to_stated_limit(
                error, base_url, model, params, provider=provider, logger=logger, cap=cap
            ):
                capped = True
                continue
            # Never while probing the output limit (cap=False): that request is meant to be refused.
            if explored or not cap or not is_exploring() or not is_rejection(error):
                raise
            explored = True
            result = _explore(send, params, error, adjusted, model=model, provider=provider, logger=logger, only=only)
            if result is _NOT_FOUND:
                raise error
            _remember(base_url, model, adjusted, provider=provider, logger=logger)
            return result
        else:
            _remember(base_url, model, adjusted, provider=provider, logger=logger)
            return result


def _remember(base_url: str, model: str, adjusted: set[str], *, provider: str, logger: logging.Logger) -> None:
    for parameter in adjusted:
        mark_unsupported(base_url, model, parameter)
    if adjusted:
        logger.info(
            "%s: remembering for model %s on this endpoint: %s not supported",
            provider,
            model,
            ", ".join(sorted(adjusted)),
        )


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
    whatever the API reported. A limit the API does not report is filled from a
    limit a rejection stated (see ``learned_limits``); a reported one is kept.
    """
    meta: dict[str, Any] = dict.fromkeys(METADATA_KEYS)
    meta.update(reported)
    if temperature_support(base_url, model) is False:
        meta["supports_temperature"] = False
    for key, value in learned_limits(base_url, model).items():
        if not meta.get(key):
            meta[key] = value
    return meta


def clear() -> None:
    with _lock:
        for memory in _MEMORY.values():
            memory.clear()
        _LIMITS.clear()
