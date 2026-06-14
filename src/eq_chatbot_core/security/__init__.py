"""
Security utilities for eq-chatbot-core.

- Encryption: API key encryption with Fernet (AES-128)
- Injection: Prompt injection detection and sanitization
- Rate Limiting: Request and token rate limiting logic
- File Validation: Secure file upload validation

IMPORTANT — these are caller-invoked primitives, NOT automatic guardrails.
The library does not call ``detect_injection`` or ``check_rate_limit`` for you;
provider calls (``chat_completion`` / ``stream_completion``) run no implicit
input filtering or rate limiting. Integrators handling untrusted input must
invoke these explicitly before dispatching to a provider. See the
"Security: caller responsibilities" section in the README for the expected
call pattern.
"""

from eq_chatbot_core.security.encryption import FernetEncryption
from eq_chatbot_core.security.file_validator import (
    FileTypeConfig,
    FileValidationResult,
    FileValidator,
    create_validator,
    is_magic_available,
)
from eq_chatbot_core.security.injection import (
    build_safe_system_prompt,
    detect_injection,
    get_injection_risk_score,
    sanitize_input,
)
from eq_chatbot_core.security.rate_limit import (
    RateLimitConfig,
    RateLimitResult,
    RateLimitStorage,
    UsageRecord,
    check_rate_limit,
    estimate_tokens,
)

__all__ = [
    # Encryption
    "FernetEncryption",
    # Injection protection
    "detect_injection",
    "sanitize_input",
    "build_safe_system_prompt",
    "get_injection_risk_score",
    # Rate limiting
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitStorage",
    "UsageRecord",
    "check_rate_limit",
    "estimate_tokens",
    # File validation
    "FileValidator",
    "FileValidationResult",
    "FileTypeConfig",
    "create_validator",
    "is_magic_available",
]
