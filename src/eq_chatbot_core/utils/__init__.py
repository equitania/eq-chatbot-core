"""
Utility functions for chatbot-core.
"""

from typing import Any

from eq_chatbot_core.utils.pdf import (
    is_pdf_conversion_available,
    pdf_to_base64_images,
    pdf_to_images,
)
from eq_chatbot_core.utils.secret_scrub import scrub_secrets
from eq_chatbot_core.utils.url_validation import validate_url

__all__ = [
    "PRICING",
    "calculate_cost",
    "is_pdf_conversion_available",
    "pdf_to_images",
    "pdf_to_base64_images",
    "scrub_secrets",
    "validate_url",
]


def __getattr__(name: str) -> Any:
    # Lazy re-export (PEP 562): an eager import here creates a circular import —
    # utils -> pricing -> services.cost_service -> providers -> local_provider -> utils —
    # which breaks any fresh `import eq_chatbot_core.services`.
    if name in ("PRICING", "calculate_cost"):
        from eq_chatbot_core.utils import pricing

        return getattr(pricing, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
