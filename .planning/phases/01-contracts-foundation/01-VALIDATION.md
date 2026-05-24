---
phase: 1
slug: contracts-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-24
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing — see pyproject.toml `[dev]` extra) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` (markers: unit, integration, local) |
| **Quick run command** | `pytest tests/unit -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds (unit, mocked) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

> Filled by the planner during plan creation. Each behavior-adding task must map to an `<automated>` verify command or a Wave 0 test stub. The five phase success criteria below are the load-bearing invariants the planner must cover.

| Invariant | Requirement | Test Type | Automated Command | Status |
|-----------|-------------|-----------|-------------------|--------|
| 12 NormalizedRealtimeEventTypes byte-for-byte | CON-* | unit | `pytest tests/unit/test_contracts.py -q` | ⬜ pending |
| `isinstance(MockRealtimeProvider(), RealtimeAdapterContract)` without [realtime] | CON-* | unit | `python -c "from eq_chatbot_core.realtime import MockRealtimeProvider, RealtimeAdapterContract; assert isinstance(MockRealtimeProvider(), RealtimeAdapterContract)"` | ⬜ pending |
| Friendly ImportError without [realtime] | CON-* | unit | `pytest tests/unit/test_realtime_import_guard.py -q` | ⬜ pending |
| All public names resolve with [realtime] | CON-* | unit | `python -c "from eq_chatbot_core.realtime import get_realtime_provider, RealtimeAdapterContract, INPUT_AUDIO_SAMPLE_RATE"` | ⬜ pending |
| `connect_with_backoff` 3-fail-then-success, mocked, delays asserted | CON-* / QUAL-02 | unit | `pytest tests/unit/test_backoff.py -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_contracts.py` — byte-for-byte string assertions for the 12 event-type constants
- [ ] `tests/unit/test_backoff.py` — mock-websockets backoff/reconnect test (asyncio sleep patched)
- [ ] `tests/unit/test_realtime_import_guard.py` — friendly ImportError when [realtime] absent
- [ ] `tests/conftest.py` — extend with mock-websockets fixture (sys.modules pattern, consistent with existing provider mocks)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `pip install eq-chatbot-core[realtime]` resolves websockets dep cleanly | CON-* | Requires a clean venv + network; not run in unit CI | In a fresh venv: `uv pip install -e ".[realtime]"` then import smoke test |

*Note: the `[realtime]`-absent friendly-ImportError path IS automatable by mocking the websockets import; only the real install resolution is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
