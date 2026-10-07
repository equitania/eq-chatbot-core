"""Constructor defaults that still exist after stage 2 (no model defaults any more).

Split out of the deleted default-model tests: their timeout / retry / organization /
endpoint assertions are still valid. Construction makes no network call.
"""

import pytest

from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from eq_chatbot_core.providers.openai_provider import OpenAIProvider

pytestmark = pytest.mark.unit


def test_openai_defaults():
    provider = OpenAIProvider(api_key="k")
    assert provider.timeout == 60.0
    assert provider.max_retries == 2
    assert provider.organization is None
    assert provider.base_url == "https://api.openai.com/v1"
    assert provider.default_model is None


def test_openai_organization_is_kept():
    assert OpenAIProvider(api_key="k", organization="org-1").organization == "org-1"


def test_anthropic_defaults():
    provider = AnthropicProvider(api_key="k")
    assert provider.timeout == 60.0
    assert provider.max_retries == 2
    assert provider.default_model is None


def test_local_defaults():
    provider = LocalLLMProvider()
    assert provider.api_key == "not-used"
    assert provider.timeout == 120.0
    assert provider.max_retries == 2
    assert provider.base_url == "http://localhost:1234/v1"
    assert provider.default_model is None
