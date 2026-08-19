# Security — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

The `eq_chatbot_core.security` package provides four building blocks for hardening LLM-backed applications: encrypted API-key storage (`encryption`), prompt-injection detection (`injection`), in-memory token-bucket rate limiting (`rate_limit`), and MIME-type-based file-upload validation (`file_validator`).

SSRF protection covers the MCP transport *and* every LLM provider. The MCP specifics are in [mcp.md](mcp.md); the provider side is described under *Provider base_url validation* below.

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
    scan_external_content,
    wrap_external_content,
)

# Quick check — detect_injection returns a (is_suspicious, matched) tuple
is_suspicious, matched = detect_injection(user_text)
if is_suspicious:
    raise UserError(f"input rejected: {matched!r}")

# Sanitize for downstream use
clean = sanitize_input(user_text)

# Numeric risk score (0.0–1.0)
score = get_injection_risk_score(user_text)

# Wrap user input in a system prompt with isolation markers
system = build_safe_system_prompt(
    base_prompt="You are a helpful assistant.",
    context=user_text,
)

# Indirect channels (MCP tool results, retrieved RAG passages): detect_injection
# covers user input only by convention — screen external content separately.
tool_suspicious, _ = scan_external_content(tool_result, source="tool:get_orders")
safe_passage = wrap_external_content(rag_passage, source="rag")  # data-fenced
```

### Rate limiting (`security.rate_limit`)

Rate-limiting logic with pluggable storage. `RateLimitStorage` is a **Protocol** — you provide the backing store (e.g. an Odoo model or a Redis-backed class); the library ships no concrete storage. `check_rate_limit` only reads counters, so the caller records usage afterwards. For race-free enforcement use `enforce_rate_limit`, which prefers an atomic `AtomicRateLimitStorage` backend and otherwise falls back to check + record.

```python
from eq_chatbot_core.security.rate_limit import (
    RateLimitConfig,
    enforce_rate_limit,
    estimate_tokens,
)

config = RateLimitConfig(
    max_requests_per_minute=10,
    max_requests_per_hour=100,
    max_tokens_per_day=100_000,
)
storage = MyRateLimitStorage()  # your RateLimitStorage / AtomicRateLimitStorage impl

# Checks the limit and records usage in one call (atomic when the backend supports it).
result = enforce_rate_limit(
    user_id="user-42",
    company_id=1,
    config=config,
    storage=storage,
    estimated_tokens=estimate_tokens(prompt_text),
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

### Provider base_url validation (v1.17.2+)

Every provider that accepts a caller-supplied `base_url` validates it with `validate_url()` at construction time: non-HTTP(S) schemes and private / link-local / cloud-metadata targets (e.g. `169.254.169.254`) raise `ValueError`.

**Since v2.1.0 that validation is also enforced at connect time.** Checking only at construction left a TOCTOU window: a hostname with a very short TTL could resolve to a public address during validation and to an internal one by the time the socket opened, carrying the `Authorization` header with it. Every provider now issues its requests through a transport from `utils/url_validation` that re-resolves on each connect. It *revalidates* rather than pinning strictly — a changed address set is re-run through the same policy and rejected only if it is private/reserved/metadata, so the routine IP rotation of CDN-fronted endpoints does not turn into connection failures in long-lived processes. For targets that are not one fixed endpoint (a URL taken from an API response, a configurable catalog location, anything followed through redirects) `build_validating_transport()` applies the full policy to whatever host each hop names. Cloud providers (`azure`, `langdock`, `openrouter`, `mammouth`, `litellm`, `ionos`, `melious`) reject private ranges; the `local` and `privatemode` providers allow them (LAN mode for on-prem model servers and for the Privatemode proxy, which is loopback by design). Fixed public default endpoints skip the check — no DNS round-trip on default construction. Explicit localhost URLs are always accepted.

### Privatemode confidentiality boundary (v3.0.0+)

The `privatemode` provider is the one case where the transport *is* the security property. Privatemode's
end-to-end encryption is produced by a local privatemode-proxy, not by this library — the library speaks
plain OpenAI Chat Completions to that proxy. Whether prompts are actually protected therefore depends
entirely on where `base_url` points, and a wrong value would fail **silently**: the caller believes the
data is encrypted while it crosses the network in the clear.

`PrivatemodeProvider` classifies the endpoint at construction, before the SDK client is ever built:

| `base_url` | Behaviour |
|------------|-----------|
| `https://…` | allowed — TLS protects the hop |
| loopback (the default `http://localhost:8080/v1`) | allowed, without a DNS lookup |
| plain HTTP → private / cluster-internal address | allowed, logged at INFO (the vendor's Helm deployment) |
| plain HTTP → **public** address | **`ValueError`**, naming the address and the three legitimate fixes |

`allow_insecure_transport=True` overrides the last row for hops protected by other means (VPN, service
mesh, IPsec) and logs a warning stating that the end-to-end guarantee does not hold. An unresolvable
hostname is warned about and deferred to the SSRF guard rather than guessed at.

### See also

- [MCP](mcp.md#english) — DNS-pinning and stdio environment whitelist for the MCP transport
- [Server mode](server-mode.md#english) — bearer-token middleware with constant-time comparison

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

Das Paket `eq_chatbot_core.security` bietet vier Bausteine zum Härten LLM-basierter Anwendungen: verschlüsselte API-Key-Speicherung (`encryption`), Prompt-Injection-Erkennung (`injection`), In-Memory-Token-Bucket-Rate-Limiting (`rate_limit`) und MIME-Type-basierte File-Upload-Validierung (`file_validator`).

Der SSRF-Schutz umfasst den MCP-Transport *und* jeden LLM-Provider. Die MCP-Details stehen in [mcp.md](mcp.md); die Provider-Seite ist unten unter *Provider base_url-Validierung* beschrieben.

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
    scan_external_content,
    wrap_external_content,
)

# Schneller Check — detect_injection liefert ein (is_suspicious, matched) Tuple
is_suspicious, matched = detect_injection(user_text)
if is_suspicious:
    raise UserError(f"input rejected: {matched!r}")

# Sanitisieren für downstream
clean = sanitize_input(user_text)

# Numerischer Risiko-Score (0.0–1.0)
score = get_injection_risk_score(user_text)

# User-Input in System-Prompt mit Isolations-Markern wrappen
system = build_safe_system_prompt(
    base_prompt="Du bist ein hilfreicher Assistent.",
    context=user_text,
)

# Indirekte Kanäle (MCP-Tool-Ergebnisse, abgerufene RAG-Passagen): detect_injection
# deckt konventionsgemäß nur Nutzereingaben ab — externe Inhalte separat prüfen.
tool_suspicious, _ = scan_external_content(tool_result, source="tool:get_orders")
safe_passage = wrap_external_content(rag_passage, source="rag")  # als Daten gefenced
```

### Rate-Limiting (`security.rate_limit`)

Rate-Limiting-Logik mit pluggable Storage. `RateLimitStorage` ist ein **Protocol** — den Speicher stellst du selbst bereit (z.B. ein Odoo-Modell oder eine Redis-gestützte Klasse); die Bibliothek liefert keinen konkreten Storage. `check_rate_limit` liest nur Zähler, der Aufrufer schreibt die Nutzung danach. Für race-freie Durchsetzung `enforce_rate_limit` verwenden — bevorzugt ein atomares `AtomicRateLimitStorage`-Backend, sonst Fallback auf check + record.

```python
from eq_chatbot_core.security.rate_limit import (
    RateLimitConfig,
    enforce_rate_limit,
    estimate_tokens,
)

config = RateLimitConfig(
    max_requests_per_minute=10,
    max_requests_per_hour=100,
    max_tokens_per_day=100_000,
)
storage = MyRateLimitStorage()  # eigene RateLimitStorage-/AtomicRateLimitStorage-Impl.

# Prüft das Limit und schreibt die Nutzung in einem Aufruf (atomar, wenn das Backend es unterstützt).
result = enforce_rate_limit(
    user_id="user-42",
    company_id=1,
    config=config,
    storage=storage,
    estimated_tokens=estimate_tokens(prompt_text),
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

### Provider base_url-Validierung (v1.17.2+)

Jeder Provider mit caller-supplied `base_url` validiert diese beim Konstruieren mit `validate_url()`: Nicht-HTTP(S)-Schemata sowie private / link-local / Cloud-Metadata-Ziele (z. B. `169.254.169.254`) lösen `ValueError` aus.

**Seit v2.1.0 wird diese Prüfung auch beim Verbindungsaufbau durchgesetzt.** Eine Prüfung ausschließlich beim Konstruieren ließ ein TOCTOU-Fenster offen: Ein Hostname mit sehr kurzer TTL konnte während der Validierung auf eine öffentliche Adresse zeigen und beim Öffnen des Sockets auf eine interne — samt `Authorization`-Header. Jeder Provider schickt seine Requests jetzt über einen Transport aus `utils/url_validation`, der bei jedem Connect neu auflöst. Er *revalidiert*, statt strikt zu pinnen: Ein geändertes Adress-Set durchläuft dieselbe Policy und wird nur abgelehnt, wenn es privat/reserviert/Metadata ist. So wird die normale IP-Rotation CDN-gestützter Endpunkte in langlebigen Prozessen nicht zum Verbindungsfehler. Für Ziele, die kein fester Endpunkt sind (eine URL aus einer API-Antwort, ein konfigurierbarer Katalog-Ort, alles mit Redirect-Verfolgung) wendet `build_validating_transport()` die vollständige Policy auf jeden einzelnen Hop an. Cloud-Provider (`azure`, `langdock`, `openrouter`, `mammouth`, `litellm`, `ionos`, `melious`) lehnen private Ranges ab; die Provider `local` und `privatemode` erlauben sie (LAN-Modus für On-Prem-Modellserver bzw. für den Privatemode-Proxy, der konstruktionsbedingt auf Loopback läuft). Feste öffentliche Default-Endpoints überspringen die Prüfung — kein DNS-Roundtrip bei Default-Konstruktion. Explizite localhost-URLs sind immer erlaubt.

### Privatemode-Vertraulichkeitsgrenze (v3.0.0+)

Beim `privatemode`-Provider **ist** der Transportweg die Sicherheitseigenschaft. Die
Ende-zu-Ende-Verschlüsselung erzeugt der lokale privatemode-proxy, nicht diese Library — die Library
spricht Klartext-OpenAI-Chat-Completions gegen diesen Proxy. Ob Prompts tatsächlich geschützt sind,
hängt damit ausschließlich davon ab, wohin `base_url` zeigt, und ein falscher Wert würde
**stillschweigend** scheitern: Der Aufrufer hält die Daten für verschlüsselt, während sie im Klartext
über das Netz gehen.

`PrivatemodeProvider` klassifiziert den Endpunkt beim Konstruieren, bevor überhaupt ein SDK-Client
gebaut wird:

| `base_url` | Verhalten |
|------------|-----------|
| `https://…` | erlaubt — TLS schützt den Hop |
| Loopback (der Default `http://localhost:8080/v1`) | erlaubt, ohne DNS-Lookup |
| Klartext-HTTP → private/cluster-interne Adresse | erlaubt, INFO-Log (das Helm-Deployment des Herstellers) |
| Klartext-HTTP → **öffentliche** Adresse | **`ValueError`** mit Nennung der Adresse und der drei legitimen Auswege |

`allow_insecure_transport=True` übersteuert die letzte Zeile für anderweitig geschützte Hops (VPN,
Service Mesh, IPsec) und protokolliert eine Warnung, dass die Ende-zu-Ende-Garantie nicht gilt. Ein
nicht auflösbarer Hostname wird gewarnt und an den SSRF-Guard weitergereicht statt geraten.

### Siehe auch

- [MCP](mcp.md#deutsch) — DNS-Pinning und stdio-Env-Whitelist für den MCP-Transport
- [Server-Mode](server-mode.md#deutsch) — Bearer-Token-Middleware mit Constant-Time-Vergleich

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
