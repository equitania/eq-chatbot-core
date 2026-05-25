---
phase: 3
slug: gemini-live-nova-sonic-stub
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/unit/realtime/test_realtime_gemini.py tests/unit/realtime/test_realtime_nova.py -x -q` |
| **Full suite command** | `pytest tests/unit/realtime/ tests/integration/ -v --cov=eq_chatbot_core` |
| **Estimated runtime** | ~8 seconds (unit only); integration skipped when env vars absent |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/realtime/test_realtime_gemini.py tests/unit/realtime/test_realtime_nova.py -x -q`
- **After every plan wave:** Run `pytest tests/unit/realtime/ -v`
- **Before `/gsd:verify-work`:** Full suite green (integration tests skip-not-fail when credentials absent)
- **Max feedback latency:** ~8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | PROV-05 (D-05) | T-03-SC | Model alias verified live; no stale alias committed | source-assertion | `grep -c "gemini-2.5-flash-preview-native-audio" src/eq_chatbot_core/realtime/providers/gemini_live.py` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | PROV-05, PROV-06 | T-03-01 | config.api_key / access_token never in module-level scope after __init__ | import+instantiation | `python -c "from eq_chatbot_core.realtime.providers.gemini_live import GeminiLiveConfig, GEMINI_LIVE_REALTIME_CAPABILITIES; c=GeminiLiveConfig(api_key='x'); assert c.model.startswith('gemini'); assert GEMINI_LIVE_REALTIME_CAPABILITIES.server_vad is False; print('OK')"` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | PROV-05, PROV-07 | T-03-01, T-03-02 | _redact_sensitive_url strips key=; _redact_sensitive_text strips bearer token | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestRedaction -x -q` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 2 | PROV-05 | T-03-01, T-03-03 | _connection_error_endpoint never contains api_key or access_token | unit | `pytest tests/unit/realtime/test_realtime_gemini.py::TestConnectionErrorEndpoint -x -q` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | PROV-08 | — | NovaSonicStub stdlib-only; no websockets or boto3 import | unit | `pytest tests/unit/realtime/test_realtime_nova.py -x -q` | ❌ W0 | ⬜ pending |
| 03-04-01 | 04 | 3 | PROV-05, PROV-08 | T-03-SC | Factory registers both providers without AWS extras | unit | `pytest tests/unit/realtime/test_factory.py -x -q` | ✅ | ⬜ pending |
| 03-05-01 | 05 | 3 | QUAL-01 | T-03-01, T-03-02 | All Gemini wire types normalize correctly; endpoint modes tested | unit | `pytest tests/unit/realtime/test_realtime_gemini.py -x -q` | ❌ W0 | ⬜ pending |
| 03-05-02 | 05 | 3 | QUAL-03 | T-03-02 | Vertex EU integration test skips cleanly when credentials absent; never logs raw token | integration | `pytest -m integration tests/integration/test_realtime_gemini_live.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

The following test files do not yet exist and must be created before or alongside the tasks that implement the behaviors they verify:

- [ ] `tests/unit/realtime/test_realtime_gemini.py` — stubs for PROV-05, PROV-06, PROV-07, QUAL-01 (created in Plan 05, Wave 3)
- [ ] `tests/unit/realtime/test_realtime_nova.py` — stubs for PROV-08, D-08 (created in Plan 03, Wave 2)
- [ ] `tests/integration/test_realtime_gemini_live.py` — stub for QUAL-03 Vertex EU path (created in Plan 05, Wave 3)
- `tests/unit/realtime/test_factory.py` — EXISTS; extended with `test_registry_contains_gemini_live`, `test_registry_contains_nova_sonic`, `test_get_realtime_provider_nova_sonic_returns_stub`, and two fail-fast tests in Plan 04 (Wave 3)

> **Note on sequencing:** `test_realtime_nova.py` ships in Plan 03 (same wave as nova.py — Wave 2), since NovaSonicStub is stdlib-only and the tests can be written alongside the stub without depending on any other Wave 2 artifact. `test_realtime_gemini.py` ships in Plan 05 (Wave 3) after gemini_live.py exists (Wave 2).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Vertex EU integration test with real `europe-west4` credentials | QUAL-03 | Requires live Vertex AI credentials (`GEMINI_VERTEX_ACCESS_TOKEN`, `VERTEX_PROJECT_ID`) — not available in CI | Run `GEMINI_VERTEX_ACCESS_TOKEN=... VERTEX_PROJECT_ID=... VERTEX_REGION=europe-west4 pytest -m integration tests/integration/test_realtime_gemini_live.py -v`; expect SESSION_READY received and clean disconnect |
| Developer API model alias live verification (D-05) | PROV-05 | Requires live `GEMINI_API_KEY` to query models list | Run `curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" \| python3 -m json.tool \| grep -i "live\|audio"` and confirm `gemini-2.5-flash-preview-native-audio-12-2025` is present |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test files created in their respective plans)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-25
