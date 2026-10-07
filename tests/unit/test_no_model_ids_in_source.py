"""No model ID, model family or model-specific value anywhere under src/ (stage 2).

Model IDs change every few weeks, so any list in the library is permanently
behind. Models come from the caller — per call or per provider instance. This
test scans every file of the package (code, docstrings, comments, packaged data)
and reports file and line for each hit. Docstring examples use placeholders such
as "your-model-id". Provider and backend names (openai, anthropic, mistral as a
URL segment, codestral as a LangDock backend, ollama) are not model IDs.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src" / "eq_chatbot_core"

# Spec, section "Guard test".
SPEC_PATTERNS = (
    r"gpt-\d",
    r"gpt-image",
    r"chatgpt",
    r"\bo[1-9](-mini|-pro|-preview)?\b",
    r"claude-",
    r"gemini-",
    r"mistral-",
    r"\bllama-",
    r"text-embedding",
    r"whisper",
    r"dall-e",
    r"kokoro",
    r"nemotron",
    r"qwen",
    r"kimi",
    r"minimax",
    r"deepseek",
    r"grok",
    r"sonar",
)
# Found by the stage-2 inventory (plan, Appendix A): IDs and family keys the
# spec patterns miss.
ADDED_PATTERNS = (
    r"\bgpt-oss",
    r"\bgpt-realtime",
    r"voxtral",
    r"codestral-\d",
    r"\bllama[\s-]?\d",
    # Names written without a dash or in prose (review of the guard, 07.10.2026).
    r"\bgpt\s?\d",
    r"\bclaude[\s-]?\d",
    r"\b(opus|sonnet|haiku)[\s-]\d",
    r"\bgemini[\s-]?\d",
    r"\b(mixtral|pixtral|magistral|devstral|ministral|gemma)",
    r"\bmistral[\s-](large|small|medium|nemo|\d)",
    r"\bmai-ds",
    r"\bcodex-mini",
    r"\baf_bella\b",
    r"""["'](claude|gemini|llama|mistral|cohere)["']""",
)
MODEL_ID = re.compile("|".join(SPEC_PATTERNS + ADDED_PATTERNS), re.IGNORECASE)


def _hits(root: Path) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        data = path.read_bytes()
        if b"\x00" in data:  # binary file: nothing a person would read as a model id
            continue
        text = data.decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            match = MODEL_ID.search(line)
            if match:
                hits.append(f"{path.relative_to(root.parent)}:{number}: {match.group(0)!r} in {line.strip()[:100]}")
    return hits


def test_no_model_ids_in_source():
    hits = _hits(SRC)
    assert not hits, "Model IDs in src/ — take them from the caller instead:\n" + "\n".join(hits)


@pytest.mark.parametrize(
    "text",
    [
        "openai",
        "OpenAIProvider",
        "anthropic",
        "AnthropicProvider",
        "/mistral/{region}/v1",
        '"codestral": "/mistral/{region}/v1",',
        'backend="codestral"',
        "ollama",
        "OLLAMA_URL",
        "your-model-id",
        "cl100k_base",
        "Gemini Live API",
    ],
)
def test_provider_and_backend_names_are_not_model_ids(text):
    assert not MODEL_ID.search(text)


@pytest.mark.parametrize(
    "text",
    [
        "gpt-5.6-luna",
        "o3",
        "o4-mini",
        "claude-sonnet-5",
        "gemini-3.7-flash",
        "text-embedding-3-small",
        "whisper-large-v3",
        "kokoro-tts-1",
        "nemotron-3-nano-30b-a3b",
        "qwen3.6-35b-a3b",
        "kimi-latest",
        "minimax-428b-m3",
        "deepseek-v3",
        "gpt-image-1",
        "dall-e-3",
        "gpt-oss-120b",
        "gpt-realtime",
        "codestral-2501",
        "llama3.2:latest",
        "gpt5",
        "GPT 5",
        "Claude 4",
        "claude3",
        "sonnet-4",
        "Gemini 2.5",
        "Llama 3",
        "mixtral-8x7b",
        "Mistral Large",
        '"claude": {',
    ],
)
def test_model_ids_are_detected(text):
    assert MODEL_ID.search(text)


def test_hits_are_reported_with_file_and_line(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "m.py").write_text('x = 1\nDEFAULT = "gpt-5.6-luna"\n', encoding="utf-8")
    # The report names the matched pattern text, not the whole id.
    assert _hits(package) == ["pkg/m.py:2: 'gpt-5' in DEFAULT = \"gpt-5.6-luna\""]


def test_data_files_are_scanned_and_binaries_skipped(tmp_path):
    """Packaged data (TOML, JSON) counts as source; a binary blob is skipped, not misread."""
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "config.toml.example").write_text('model = "claude-sonnet-5"\n', encoding="utf-8")
    (package / "blob.bin").write_bytes(b"\x00\x01gpt-5\x00")
    assert _hits(package) == ["pkg/config.toml.example:1: 'claude-' in model = \"claude-sonnet-5\""]
