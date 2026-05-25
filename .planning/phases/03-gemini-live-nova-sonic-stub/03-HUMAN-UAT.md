---
status: partial
phase: 03-gemini-live-nova-sonic-stub
source: [03-VERIFICATION.md]
started: 2026-05-25T16:05:00Z
updated: 2026-05-25T16:05:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. QUAL-03 — Gemini Live Vertex EU live roundtrip
expected: Test passes (not skipped) — SESSION_READY received as first normalized event, PCM16 silence accepted, commit_client_turn completes without error, async context manager exits cleanly on the europe-west4 endpoint.
result: [pending]
how-to-run: |
  uv pip install -e ".[realtime]"
  export GEMINI_VERTEX_ACCESS_TOKEN="$(gcloud auth print-access-token)"
  export VERTEX_PROJECT_ID="<your-eu-project>"
  .venv/bin/python -m pytest tests/integration/test_realtime_gemini_live.py -v
why-human: Requires GEMINI_VERTEX_ACCESS_TOKEN + VERTEX_PROJECT_ID and the [realtime] extra (websockets). Without them pytest.importorskip / skipif fires at collection (exit 5 = no tests collected — correct skip behavior, not a PASS). A full QUAL-03 pass needs a real Vertex EU endpoint roundtrip.

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
