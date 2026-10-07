"""Introspect the public provider surface that consumers (Odoo, CLI, server) rely on.

Run as a script to (re)write tests/compat/public_api.json — only ever before a
deliberate, reviewed API change:  uv run python -m tests.compat.snapshot
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path(__file__).with_name("public_api.json")

CLASSES = [
    ("eq_chatbot_core.providers.openai_provider", "OpenAIProvider"),
    ("eq_chatbot_core.providers.mammouth_provider", "MammouthProvider"),
    ("eq_chatbot_core.providers.openrouter_provider", "OpenRouterProvider"),
    ("eq_chatbot_core.providers.local_provider", "LocalLLMProvider"),
    ("eq_chatbot_core.providers.langdock_provider", "LangDockProvider"),
    ("eq_chatbot_core.providers.langdock_provider", "LangDockAgentManager"),
    ("eq_chatbot_core.providers.langdock_provider", "LangDockKnowledgeManager"),
    ("eq_chatbot_core.providers.ionos_provider", "IonosProvider"),
    ("eq_chatbot_core.providers.melious_provider", "MeliousProvider"),
    ("eq_chatbot_core.providers.litellm_provider", "LiteLLMProvider"),
    ("eq_chatbot_core.providers.privatemode_provider", "PrivatemodeProvider"),
]


def _describe(cls: type) -> dict[str, Any]:
    methods = {}
    for name, member in inspect.getmembers(cls):
        if name.startswith("_") and name != "__init__":
            continue
        if inspect.isfunction(member):
            methods[name] = str(inspect.signature(member))
        elif isinstance(inspect.getattr_static(cls, name), property):
            methods[name] = "property"
    constants = {}
    for name, value in vars_all(cls).items():
        if name.isupper() and not callable(value):
            # Ensure deterministic repr for frozensets (sort the elements)
            if isinstance(value, frozenset):
                sorted_items = ", ".join(repr(x) for x in sorted(value, key=str))
                sorted_repr = f"frozenset({{{sorted_items}}})"
                constants[name] = sorted_repr
            else:
                constants[name] = repr(value)
    return {"members": methods, "constants": constants}


def vars_all(cls: type) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        merged.update(vars(klass))
    return merged


def public_surface() -> dict[str, Any]:
    import importlib

    import eq_chatbot_core.providers as providers

    surface: dict[str, Any] = {"providers.__all__": sorted(providers.__all__)}
    for module_name, class_name in CLASSES:
        cls = getattr(importlib.import_module(module_name), class_name)
        surface[class_name] = _describe(cls)
    return surface


if __name__ == "__main__":
    SNAPSHOT_PATH.write_text(json.dumps(public_surface(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {SNAPSHOT_PATH}")
