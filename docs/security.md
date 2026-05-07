# Security — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

The `eq_chatbot_core.security` package provides four building blocks for hardening LLM-backed applications: encrypted API-key storage (`encryption`), prompt-injection detection (`injection`), in-memory token-bucket rate limiting (`rate_limit`), and MIME-type-based file-upload validation (`file_validator`).

DNS-rebinding and SSRF protection for the MCP transport live in a sibling package — see [mcp.md](mcp.md).

### Encryption (`security.encryption`)

Symmetric authenticated encryption based on Fernet (AES-128-CBC + HMAC-SHA256). Keys are URL-safe base64-encoded; tokens carry a timestamp.

```python
from eq_chatbot_core.security.encryption import FernetEncryption

encryption = FernetEncryption()
key = encryption.generate_key()             # bytes — store securely (env, keychain, KMS)

token = encryption.encrypt("sk-secret-key", key)
plaintext = encryption.decrypt(token, key)  # raises if key is wrong or token tampered
```

Use cases: persisting API keys to disk, encrypting per-tenant config.

### Prompt-injection detection (`security.injection`)

Pattern-based detector that flags common injection attempts (role override, instruction smuggling, delimiter abuse). Detection runs on the **raw input** — sanitization happens afterwards (this ordering was a v1.5.1 fix; the previous version escaped HTML before pattern matching, silently bypassing angle-bracket and paren-based patterns).

```python
from eq_chatbot_core.security.injection import (
    detect_injection,
    sanitize_input,
    build_safe_system_prompt,
    get_injection_risk_score,
)

# Quick yes/no check
if detect_injection(user_text):
    raise UserError("input rejected")

# Sanitize for downstream use
clean = sanitize_input(user_text)

# Numeric risk score (0.0–1.0)
score = get_injection_risk_score(user_text)

# Wrap user input in a system prompt with isolation markers
system = build_safe_system_prompt(
    base_prompt="You are a helpful assistant.",
    user_context=user_text,
)
```

### Rate limiting (`security.rate_limit`)

Token-bucket rate limiter with pluggable storage. The default storage is in-memory and **per-process**; pass a custom `RateLimitStorage` implementation for distributed setups.

```python
from eq_chatbot_core.security.rate_limit import (
    RateLimitConfig,
    RateLimitStorage,
    check_rate_limit,
    estimate_tokens,
)

config = RateLimitConfig(
    requests_per_minute=60,
    tokens_per_minute=100_000,
)
storage = RateLimitStorage()

result = check_rate_limit(
    user_id="user-42",
    estimated_tokens=estimate_tokens(prompt_text),
    config=config,
    storage=storage,
)
if not result.allowed:
    raise RateLimitedError(retry_after=result.retry_after)
```

`estimate_tokens()` uses a tiktoken-based heuristic suitable for pre-flight budget checks.

### File validation (`security.file_validator`)

MIME-type sniffing via `puremagic` (pure Python — no `libmagic` system dependency). Requires the `[security]` extra:

```bash
uv pip install eq-chatbot-core[security]
```

```python
from eq_chatbot_core.security.file_validator import (
    create_validator,
    is_magic_available,
)

if not is_magic_available():
    raise RuntimeError("install eq-chatbot-core[security]")

validator = create_validator(allowed_types=["image/png", "image/jpeg", "application/pdf"])

result = validator.validate(file_bytes, declared_filename="upload.png")
if not result.valid:
    raise UserError(result.reason)
```

Detection is content-based — a `.txt` file with a JPEG header is rejected as `image/jpeg`. Use this on every uploaded file before passing to a vision-capable model.

### Provider-level redirect protection

Standalone HTTP calls inside cloud providers (`mammouth`, `langdock`) disable redirect following (`follow_redirects=False`) to defeat SSRF via DNS-based redirect manipulation. This is automatic — no caller action needed.

### See also

- [MCP](mcp.md#english) — DNS-pinning and stdio environment whitelist for the MCP transport
- [Server mode](server-mode.md#english) — bearer-token middleware with constant-time comparison

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

Das Paket `eq_chatbot_core.security` bietet vier Bausteine zum Härten LLM-basierter Anwendungen: verschlüsselte API-Key-Speicherung (`encryption`), Prompt-Injection-Erkennung (`injection`), In-Memory-Token-Bucket-Rate-Limiting (`rate_limit`) und MIME-Type-basierte File-Upload-Validierung (`file_validator`).

DNS-Rebinding- und SSRF-Schutz für den MCP-Transport liegen in einem Schwester-Paket — siehe [mcp.md](mcp.md).

### Verschlüsselung (`security.encryption`)

Symmetrische authentifizierte Verschlüsselung basierend auf Fernet (AES-128-CBC + HMAC-SHA256). Keys sind URL-safe-Base64-encoded; Tokens enthalten einen Timestamp.

```python
from eq_chatbot_core.security.encryption import FernetEncryption

encryption = FernetEncryption()
key = encryption.generate_key()             # bytes — sicher speichern (env, keychain, KMS)

token = encryption.encrypt("sk-secret-key", key)
plaintext = encryption.decrypt(token, key)  # wirft bei falschem Key oder manipuliertem Token
```

Anwendungsfälle: API-Keys auf Disk persistieren, per-Tenant-Configs verschlüsseln.

### Prompt-Injection-Erkennung (`security.injection`)

Pattern-basierter Detektor, der gängige Injection-Versuche erkennt (Rollen-Override, Instruction-Smuggling, Delimiter-Missbrauch). Detection läuft auf dem **rohen Input** — Sanitization danach (diese Reihenfolge war ein v1.5.1-Fix; die vorherige Version escapte HTML vor Pattern-Matching, was Winkelklammer- und Klammer-Patterns stillschweigend umging).

```python
from eq_chatbot_core.security.injection import (
    detect_injection,
    sanitize_input,
    build_safe_system_prompt,
    get_injection_risk_score,
)

# Schneller Ja/Nein-Check
if detect_injection(user_text):
    raise UserError("input rejected")

# Sanitisieren für downstream
clean = sanitize_input(user_text)

# Numerischer Risiko-Score (0.0–1.0)
score = get_injection_risk_score(user_text)

# User-Input in System-Prompt mit Isolations-Markern wrappen
system = build_safe_system_prompt(
    base_prompt="Du bist ein hilfreicher Assistent.",
    user_context=user_text,
)
```

### Rate-Limiting (`security.rate_limit`)

Token-Bucket-Rate-Limiter mit pluggable Storage. Default-Storage ist In-Memory und **per-Prozess**; eigene `RateLimitStorage`-Implementierung für verteilte Setups.

```python
from eq_chatbot_core.security.rate_limit import (
    RateLimitConfig,
    RateLimitStorage,
    check_rate_limit,
    estimate_tokens,
)

config = RateLimitConfig(
    requests_per_minute=60,
    tokens_per_minute=100_000,
)
storage = RateLimitStorage()

result = check_rate_limit(
    user_id="user-42",
    estimated_tokens=estimate_tokens(prompt_text),
    config=config,
    storage=storage,
)
if not result.allowed:
    raise RateLimitedError(retry_after=result.retry_after)
```

`estimate_tokens()` verwendet eine tiktoken-basierte Heuristik, geeignet für Pre-Flight-Budget-Checks.

### File-Validation (`security.file_validator`)

MIME-Type-Sniffing via `puremagic` (pure Python — keine `libmagic`-System-Abhängigkeit). Braucht das `[security]`-Extra:

```bash
uv pip install eq-chatbot-core[security]
```

```python
from eq_chatbot_core.security.file_validator import (
    create_validator,
    is_magic_available,
)

if not is_magic_available():
    raise RuntimeError("install eq-chatbot-core[security]")

validator = create_validator(allowed_types=["image/png", "image/jpeg", "application/pdf"])

result = validator.validate(file_bytes, declared_filename="upload.png")
if not result.valid:
    raise UserError(result.reason)
```

Erkennung ist Content-basiert — eine `.txt`-Datei mit JPEG-Header wird als `image/jpeg` abgelehnt. Vor jedem Upload an ein Vision-fähiges Modell anwenden.

### Provider-Level Redirect-Schutz

Standalone-HTTP-Calls in Cloud-Providern (`mammouth`, `langdock`) deaktivieren Redirect-Following (`follow_redirects=False`) um SSRF via DNS-basierte Redirect-Manipulation zu unterbinden. Automatisch — kein Caller-Eingriff nötig.

### Siehe auch

- [MCP](mcp.md#deutsch) — DNS-Pinning und stdio-Env-Whitelist für den MCP-Transport
- [Server-Mode](server-mode.md#deutsch) — Bearer-Token-Middleware mit Constant-Time-Vergleich

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
