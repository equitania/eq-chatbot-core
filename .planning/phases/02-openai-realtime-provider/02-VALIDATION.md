---
phase: 2
slug: openai-realtime-provider
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-24
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml ([tool.pytest.ini_options]) |
| **Quick run command** | `pytest tests/unit/realtime/test_realtime_openai.py -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds (unit, mocked) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/realtime/test_realtime_openai.py -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {N}-01-01 | 01 | 1 | PROV-XX | — | N/A | unit | `pytest tests/unit/realtime/test_realtime_openai.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Planner fills this map per task. See `02-RESEARCH.md` → "## Validation Architecture" for the unit surfaces (connect lifecycle, iter_normalized_events replay, close lifecycle, capability assertions) and the live integration test (SESSION_READY → PCM16 chunk → clean close).*

---

## Wave 0 Requirements

- [ ] `tests/unit/realtime/test_realtime_openai.py` — stubs for PROV-01..04
- [ ] `tests/unit/realtime/conftest.py` — reuse existing AsyncMock websockets fixture (Phase 1)
- [ ] Integration test scaffold (skipped when `OPENAI_API_KEY` absent) — QUAL-03 (OpenAI portion)

*Existing pytest infrastructure (Phase 1 conftest) covers most fixtures; OpenAI-specific suite is new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live SESSION_READY → PCM16 → close round-trip | QUAL-03 (OpenAI) | Requires real `OPENAI_API_KEY`; skipped in CI | `OPENAI_API_KEY=... pytest tests/integration/realtime/test_realtime_openai_live.py -q` |

*Integration test is automated but gated on key presence; treated as manual-equivalent in CI.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
