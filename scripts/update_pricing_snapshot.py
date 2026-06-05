#!/usr/bin/env python3
"""Refresh the bundled model-pricing snapshot.

Downloads the latest LiteLLM ``model_prices_and_context_window.json`` and writes
it to ``src/eq_chatbot_core/data/model_prices.json``. Run at release time to keep
the offline pricing fallback current.

Usage:
    python scripts/update_pricing_snapshot.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)
TARGET = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src", "eq_chatbot_core", "data", "model_prices.json")
)


def main() -> int:
    print(f"Fetching {URL} ...")
    with urllib.request.urlopen(URL, timeout=30) as resp:  # noqa: S310 (trusted URL)
        data = json.load(resp)
    if not isinstance(data, dict) or len(data) < 100:
        print("Refusing to write: response does not look like the pricing database.", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=0, sort_keys=True)
    print(f"Wrote {len(data)} entries -> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
