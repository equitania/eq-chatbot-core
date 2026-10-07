# Task 8 review (0e4ec0d..0dc944b)

Spec compliance: ✅
Quality: Approved (Minor findings only)

## Spec compliance
- All 19 spec patterns are present verbatim in SPEC_PATTERNS, case-insensitive, scan covers every file under src/eq_chatbot_core incl. data/config.toml.example (the only non-.py file; py.typed is empty).
- Provider/backend names (openai, anthropic, mistral URL segment, codestral backend, ollama, "Gemini Live API") do not match; tested as non-matches.
- Hits carry file and line. Report-format test expects 'gpt-5' per ruling 1.
- Docstrings follow the brief; they describe the behaviour correctly (no default model, ModelNotSpecifiedError, list_models, vendor/ prefix, google ids without "models/").

## Findings

### Critical: none
### Important: none

### Minor 1: blind spots for families written without a dash or in prose
Probed with MODEL_ID.search; NOT matched: "gpt5", "gpt4o", "GPT4", "GPT 5", "claude3", "Claude Opus", "Claude 4", "sonnet-4", "opus-4", "Mistral Large", "mistral/v1" (fine), "Llama 3", "gemini2.5", "Gemini 2.5", "gemma-3", "phi-4", "mixtral", "pixtral", "magistral", "devstral", "ministral", "command-r", "bge-m3", "tts-1", "imagen-4", "sora-2", "glm-4".
Matched correctly: "GPT-5", "gpt-4o", "llama3", "llama-3", "meta-llama/Llama-3.3", "mistral-large", "mistralai/Mistral-7B"? (no: "mistralai/" lacks "mistral-"; only the "-7B" id slips through only when written like that; "Mistral-7B" does match "mistral-").
Fix (test file lines 21-54), add to ADDED_PATTERNS: `r"\bgpt\s?\d"`, `r"\bclaude[\s-]?\d"`, `r"\b(opus|sonnet|haiku)[\s-]\d"`, `r"\bgemini[\s-]?\d"`, `r"\bllama[\s-]?\d"` (replaces `\bllama\d`), `r"\b(mixtral|pixtral|magistral|devstral|ministral|gemma)"`, `r"\bmistral[\s-](large|small|medium|nemo|\d)"`. Add matching cases to test_model_ids_are_detected (34 -> more parametrized cases; update the "34 passed" expectation).

### Minor 2: false positives
- `\bo[1-9]...\b` matches the prose "o1"/"o3" as a standalone token (e.g. "foo o3 bar"). Hex strings do not trigger it (no letter o in hex). Acceptable; document in the module docstring that standalone o1..o9 is deliberate.
- Substring patterns (spec-mandated, no word boundary): "grok" (grokking), "sonar" (sonarqube), "whisper" (whisperer), "kimi", "qwen". Currently no hit in src/, so harmless; a legitimate future word would need rewording. Optional: `\bgrok`, `\bsonar\b|\bsonar-`, but that deviates from the spec patterns, so leave as is and note it.

### Minor 3: file reading robustness
`_hits` uses `read_text(errors="replace")`, so binary files do not crash it, but a binary file (e.g. a future .so/.png/.json blob) is scanned as garbage and report lines would be noisy. Fix: skip files whose bytes contain b"\x00" (`data = path.read_bytes(); if b"\x00" in data: continue; text = data.decode("utf-8", "replace")`). Not currently exercised (only .py and config.toml.example exist).

### Minor 4: no test that non-.py files are scanned
Add to the report test a second file `pkg/data.toml` with a model id and assert the hit, to pin the "JSON/TOML data" requirement of the spec.
