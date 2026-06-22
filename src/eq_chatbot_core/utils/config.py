"""User configuration file for the eq-chatbot CLI.

Loads a TOML config from ``~/.config/eq-chatbot/config.toml`` (XDG-aware, with an
``EQ_CHATBOT_CONFIG`` override) so users can store provider keys, base URLs, default
models and chat defaults on the host instead of passing them on every call.

This is a CLI-layer concern only — the library providers never read this file; the
CLI resolves values here and passes them to ``get_provider()`` explicitly.

Precedence the CLI applies (highest first): flag > provider-specific env var >
``LLM_API_KEY`` env > this config file > built-in default.
"""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib


class ConfigError(Exception):
    """Raised when the config file exists but cannot be read or parsed."""


# Cache parsed config per path keyed by mtime so repeated lookups within a single
# CLI invocation do not re-read the file (and the permission warning fires once).
_cache: dict[str, tuple[int, dict[str, Any]]] = {}
_warned: set[str] = set()


def reset_cache() -> None:
    """Clear the in-process config cache (used by tests for isolation)."""
    _cache.clear()
    _warned.clear()


def config_path() -> Path:
    """Resolve the config file path.

    Order: ``EQ_CHATBOT_CONFIG`` override > ``$XDG_CONFIG_HOME/eq-chatbot/config.toml``
    > ``~/.config/eq-chatbot/config.toml``.
    """
    override = os.environ.get("EQ_CHATBOT_CONFIG")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "eq-chatbot" / "config.toml"


def load_config() -> dict[str, Any]:
    """Load and parse the config file. Missing file -> empty dict.

    Warns once (stderr) if the file is group/other-readable. Raises ConfigError on
    malformed TOML.
    """
    path = config_path()
    try:
        st = path.stat()
    except FileNotFoundError:
        return {}
    except OSError as exc:  # pragma: no cover - unusual FS errors
        raise ConfigError(f"Cannot access config file {path}: {exc}") from exc

    key = str(path)
    cached = _cache.get(key)
    if cached is not None and cached[0] == st.st_mtime_ns:
        return cached[1]

    if st.st_mode & 0o077 and key not in _warned:
        sys.stderr.write(f"Warning: {path} is readable by others; run: chmod 600 {path}\n")
        _warned.add(key)

    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Failed to parse config file {path}: {exc}") from exc
    except OSError as exc:  # pragma: no cover - unusual FS errors
        raise ConfigError(f"Cannot read config file {path}: {exc}") from exc

    _cache[key] = (st.st_mtime_ns, data)
    return data


def _provider_section(provider: str | None) -> dict[str, Any]:
    if not provider:
        return {}
    providers = load_config().get("providers")
    if not isinstance(providers, dict):
        return {}
    section = providers.get(provider.lower())
    return section if isinstance(section, dict) else {}


def _str_field(section: dict[str, Any], field: str) -> str | None:
    value = section.get(field)
    return value if isinstance(value, str) and value else None


def config_api_key(provider: str | None) -> str | None:
    """Return the configured API key for a provider, or None."""
    return _str_field(_provider_section(provider), "api_key")


def config_base_url(provider: str | None) -> str | None:
    """Return the configured base URL for a provider, or None."""
    return _str_field(_provider_section(provider), "base_url")


def config_model(provider: str | None) -> str | None:
    """Return the configured default model for a provider, or None."""
    return _str_field(_provider_section(provider), "model")


def config_default_provider() -> str | None:
    """Return the configured default provider, or None."""
    value = load_config().get("default_provider")
    return value if isinstance(value, str) and value else None


def _defaults_section() -> dict[str, Any]:
    section = load_config().get("defaults")
    return section if isinstance(section, dict) else {}


def config_temperature() -> float | None:
    """Return the configured default temperature, or None."""
    value = _defaults_section().get("temperature")
    # bool is a subclass of int; exclude it explicitly.
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) else None


def config_max_tokens() -> int | None:
    """Return the configured default max_tokens, or None."""
    value = _defaults_section().get("max_tokens")
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def template_text() -> str:
    """Return the bundled config template (config.toml.example)."""
    return resources.files("eq_chatbot_core.data").joinpath("config.toml.example").read_text(encoding="utf-8")


def write_template(dest: Path | None = None, *, force: bool = False) -> Path:
    """Write the config template to ``dest`` (default: config_path()) with mode 0600.

    Refuses to overwrite an existing file unless ``force`` is set.
    """
    target = dest if dest is not None else config_path()
    if target.exists() and not force:
        raise ConfigError(f"{target} already exists; pass --force to overwrite")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template_text(), encoding="utf-8")
    target.chmod(0o600)
    # Invalidate any cached entry for this path so a subsequent read sees the new file.
    _cache.pop(str(target), None)
    return target


def redact(value: str) -> str:
    """Mask a secret for display: keep only the last 4 characters."""
    if len(value) <= 4:
        return "****"
    return f"…{value[-4:]}"
