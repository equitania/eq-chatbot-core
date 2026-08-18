"""Backward-compatibility shim for the pre-services pricing location.

``PRICING`` and ``calculate_cost`` moved to :mod:`eq_chatbot_core.services.cost_service`.
This module is kept so existing imports (notably the Odoo-side eq_chatbot bundle)
keep working; new code should import from ``services.cost_service`` directly.

Deliberately not removed: it is public API surface of a published package, so
dropping it would be a breaking change for consumers that never got a warning.
"""

from eq_chatbot_core.services.cost_service import PRICING, calculate_cost

__all__ = ["PRICING", "calculate_cost"]
