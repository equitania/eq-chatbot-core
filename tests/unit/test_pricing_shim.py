"""The utils.pricing shim must keep re-exporting the moved pricing API."""

import pytest

pytestmark = pytest.mark.unit


def test_shim_reexports_the_canonical_objects():
    from eq_chatbot_core.services import cost_service
    from eq_chatbot_core.utils import pricing

    assert pricing.PRICING is cost_service.PRICING
    assert pricing.calculate_cost is cost_service.calculate_cost


def test_shim_exports_are_declared():
    from eq_chatbot_core.utils import pricing

    assert set(pricing.__all__) == {"PRICING", "calculate_cost"}
