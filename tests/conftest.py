"""
Pytest fixtures for chatbot-core tests.
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = MagicMock()

    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(content="Hello! How can I help?", tool_calls=None),
            finish_reason="stop",
        )
    ]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=8)
    mock_response.model = "gpt-4o"
    mock_response.model_dump.return_value = {"id": "test"}

    client.chat.completions.create.return_value = mock_response

    return client


@pytest.fixture
def sample_messages():
    """Sample message list for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]


@pytest.fixture
def encryption_key():
    """Generate encryption key for tests."""
    from eq_chatbot_core.security.encryption import FernetEncryption
    return FernetEncryption.generate_key()
