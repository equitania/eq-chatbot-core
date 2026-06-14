"""
Secret scrubbing for logs and error surfaces.

Provider SDKs and HTTP error bodies frequently embed credentials (API keys,
bearer tokens) or sensitive query parameters. Before such text is logged or
returned to a caller, run it through :func:`scrub_secrets` to mask known
secret shapes. This is defense-in-depth: it does not replace not logging
secrets in the first place, but limits accidental exposure.
"""

import re

_MASK = "***"

# Each entry masks only the secret-bearing capture group, preserving surrounding
# context so messages stay useful for debugging.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Bearer <token>
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{6,}"), r"\1" + _MASK),
    # Known API-key prefixes (sk-ant-, sk-or-, sk-, ld-, mm-). Longer prefixes
    # are listed first so alternation matches them before the shorter "sk-".
    (
        re.compile(r"\b(?:sk-ant-|sk-or-|sk-|ld-|mm-)[A-Za-z0-9._\-]{6,}"),
        _MASK,
    ),
    # Secret-bearing query parameters: ?api_key=..., &key=..., &token=...
    (
        re.compile(r"(?i)([?&](?:api[_-]?key|key|token|access[_-]?token)=)[^&\s\"']+"),
        r"\1" + _MASK,
    ),
    # JSON / key-value style: "api_key": "...", authorization=..., token: ...
    (
        re.compile(
            r"(?i)(\"?(?:api[_-]?key|authorization|token|secret|password)\"?\s*[:=]\s*\"?)"
            r"[A-Za-z0-9._\-]{6,}"
        ),
        r"\1" + _MASK,
    ),
]


def scrub_secrets(text: str) -> str:
    """Mask known credential shapes in arbitrary text.

    Args:
        text: Text that may contain API keys, bearer tokens, or secret
            query parameters (e.g. a logger message or HTTP error body).

    Returns:
        The text with detected secrets replaced by ``***``. Non-secret content
        is preserved. Returns the input unchanged if it is empty or not a str.
    """
    if not text or not isinstance(text, str):
        return text

    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text
