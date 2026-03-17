# Release Notes

## Version 1.3.0 (17.03.2026)

### Added
- Google Vertex AI provider with Gemini 2.0/2.5 model support via `google-genai` SDK
- Vertex AI uses Application Default Credentials (ADC) — no API key needed
- EU region support (europe-west1, europe-west3, europe-west4) for GDPR compliance
- 44 unit tests + 5 integration tests for Vertex provider
- `[vertex]` optional dependency group in pyproject.toml
- Gemini 2.0-flash and 2.0-flash-lite pricing in cost_service

### Changed
- CLI: Added `vertex` to cloud providers with API-key bypass (uses ADC)
- Factory: `get_provider("vertex", project="...", location="...")` registration
- README.md: Bilingual documentation with Vertex AI usage examples
- Test infrastructure: Vertex module group in conftest.py report generation

### Fixed
- LangDock Knowledge Manager endpoint corrections (from v1.2.1)

## Version 1.2.1 (14.03.2026)

### Fixed
- LangDock Knowledge Manager endpoint corrections

## Version 1.2.0 (13.03.2026)

### Changed
- Azure model catalog expansion + temperature constraint fixes
- LangDock export: switch from JSON to Markdown format
