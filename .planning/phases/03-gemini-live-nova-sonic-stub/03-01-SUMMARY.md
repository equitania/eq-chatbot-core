---
phase: 03-gemini-live-nova-sonic-stub
plan: "01"
subsystem: testing
tags: [gemini-live, model-alias, verification, realtime]

requires:
  - phase: 02-realtime-foundation
    provides: BaseRealtimeWebsocketClient + realtime provider scaffold
provides:
  - Verified, live-accepted Gemini Live model alias for GeminiLiveConfig.model default
  - Captain decision: gemini-3.1-flash-live-preview (overrides RESEARCH.md 2.5 native-audio assumption)
affects: [gemini_live.py, GeminiLiveConfig, test_realtime_gemini]

tech-stack:
  added: []
  patterns:
    - "Model alias verified against live ai.google.dev docs at phase start (D-05 / PITFALL-20)"

key-files:
  created:
    - .planning/phases/03-gemini-live-nova-sonic-stub/03-01-SUMMARY.md
  modified: []

key-decisions:
  - "GeminiLiveConfig.model default = gemini-3.1-flash-live-preview (Captain decision 2026-05-25)"
  - "Chose newest Live model (3.1, March 2026) over 2.5 native-audio per D-04 floating-alias principle"
  - "Affective dialog must NOT be default-enabled — unsupported on gemini-3.1-flash-live-preview"

patterns-established:
  - "Setup envelope must send models/-prefixed id (models/gemini-3.1-flash-live-preview) per PITFALL"

requirements-completed: [PROV-05]

duration: 8min
completed: 2026-05-25
---

# Phase 3 / Plan 01: Verified Model Alias Summary

**Gemini Live model alias verified live against ai.google.dev — Captain selected `gemini-3.1-flash-live-preview` as the GeminiLiveConfig.model default, overriding the RESEARCH.md 2.5-native-audio assumption.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-05-25
- **Tasks:** 1 (blocking human-verify checkpoint)
- **Files modified:** 0 (verification-only plan, no production code)

## Verified Model Alias

| Field | Value |
|-------|-------|
| **Chosen alias (GeminiLiveConfig.model default)** | `gemini-3.1-flash-live-preview` |
| **Verification method** | ai.google.dev official model docs (GEMINI_API_KEY absent → documented docs fallback used) |
| **Date verified** | 2026-05-25 |
| **Source** | https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-live-preview |
| **Live API** | Supported |
| **Inputs / Outputs** | Text, images, audio, video → Text and audio |
| **Output token limit** | 65,536 |
| **Latest update** | March 2026 |
| **Knowledge cutoff** | January 2025 |
| **Affective dialog** | **NOT supported** (explicitly noted on the Live capabilities guide) |
| **Vertex AI note** | Assumed same alias; Vertex model list not queried (no credentials). Confirm `gemini-3.1-flash-live-preview` against the Vertex model list before relying on the EU/Vertex path (RESEARCH A3). |

### Both live-listed Live API models on 2026-05-25 (for the record)

1. `gemini-3.1-flash-live-preview` — **CHOSEN.** Newest Live model (March 2026), A2A, output limit 65,536. No affective dialog.
2. `gemini-2.5-flash-native-audio-preview-12-2025` — flagship native-audio model, affective dialog supported, output limit 8,192. Not chosen.

Dead aliases confirmed avoided: `gemini-2.0-flash` / `gemini-2.0-flash-001` (shutdown June 1 2026), `gemini-live-2.5-flash-...-09-2025` (removed March 2026).

## Decisions Made

- **Captain decision (2026-05-25):** default to `gemini-3.1-flash-live-preview` rather than the 2.5 native-audio model assumed in RESEARCH.md. Rationale: it is the newest Live-API model and best matches D-04 ("floating alias tracks Google's current Live model").

## Deviations from Plan

### Deviation: chosen alias differs from RESEARCH.md assumption

- **Found during:** Task 1 (live verification).
- **Issue:** RESEARCH.md / Plan 02 assumed `gemini-2.5-flash-preview-native-audio-12-2025` (word order `preview-native-audio`). That exact string is **not** a valid model code — the live 2.5 model code is `gemini-2.5-flash-native-audio-preview-12-2025` (`native-audio-preview`). Separately, a newer model `gemini-3.1-flash-live-preview` now exists.
- **Resolution:** Captain selected `gemini-3.1-flash-live-preview` via blocking checkpoint.
- **Impact:** Plan 02 must embed the chosen alias, not the assumed one.

## ⚠ REQUIRED for Plan 02 executor (read before committing gemini_live.py)

1. **Set the default to the verified alias:**
   ```python
   model: str = "gemini-3.1-flash-live-preview"  # verified live 2026-05-25 (D-05); newest Live API model
   ```
   Do NOT use `gemini-2.5-flash-preview-native-audio-12-2025` (invalid string) or any `2.0-flash` / `09-2025` alias.
2. **Affective dialog is UNSUPPORTED on this model.** Do NOT enable `enable_affective_dialog` / `proactive_audio` by default with this alias — it will be rejected or ignored. Keep it off unless the consumer explicitly opts in and overrides the model to a native-audio alias.
3. **Setup envelope prefix:** the BidiGenerateContent setup message expects the `models/`-prefixed id (`models/gemini-3.1-flash-live-preview`). Normalize the bare alias to the prefixed form when building the setup payload (RESEARCH PITFALL).
4. **Vertex AI:** alias assumed identical on Vertex but unverified — Plan 05's Vertex integration test should confirm, and fall back / skip gracefully if Vertex rejects it.

## Issues Encountered

- `GEMINI_API_KEY` not present in environment → used the plan's documented docs fallback (ai.google.dev model pages) instead of the live `curl models?key=` query. Result is equally authoritative for the alias string.

## Next Phase Readiness

- Wave 2 (Plans 02 + 03) unblocked. Plan 02 has its verified default + the affective-dialog/prefix constraints above.

---
*Phase: 03-gemini-live-nova-sonic-stub*
*Completed: 2026-05-25*
