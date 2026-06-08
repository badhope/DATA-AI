# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Authentication defaults to deny: every route now requires an
  `Authorization: Bearer <key>` header unless `DATA_AI_DEV_MODE=true`.
  The whitelist is `DATA_AI_API_KEYS` (comma-separated). Default-on
  unauthenticated access has been removed.
- The skill execution endpoint (`POST /v1/skills/{id}/execute`) is gated
  behind `DATA_AI_SKILL_EXEC=1`. A default install can no longer shell
  out, even if auth is bypassed.
- CORS is opt-in: `DATA_AI_CORS_ORIGINS` lists the allowed origins.
  Empty (the default) emits no CORS headers at all.

### Internationalization
- Server-side catalog of error messages in English and 简体中文,
  selected per request from `X-Locale` or `Accept-Language`.
- Agent system prompt is amended per request so the model replies in the
  user's language.

### Documentation
- Rewrote `docs/ARCHITECTURE.md` to match the actual code (no more
  references to frameworks we don't use).
- Rewrote `docs/INSTALLATION.md`, `docs/CONFIGURATION.md`, and the
  example TOML to match the real `data_ai.utils.config.Settings` loader.
- Rewrote `README.md` and `README_zh.md` to drop the marketing tone and
  the imaginary stack diagrams. The new versions describe the project
  as it is.
- Removed 22 AI-generated planning / progress / implementation
  documents that didn't survive a code review.

### CI / testing
- New unit tests for the auth dependency, the i18n catalog and
  negotiator, and the offline LLM client. Run with
  `pytest tests/unit/`.
- `.github/workflows/ci.yml` rewritten to run a Python matrix
  (3.10 / 3.11 / 3.12), `ruff check` + `ruff format --check`, the full
  test suite, the frontend `tsc -b` + `npm run build`, and a sdist /
  wheel build with `twine check`.

## [2.0.0] - 2026-05

### Changed
- Package renamed from internal codename to `data-ai` on PyPI.
- LLM manager now exposes 19 providers through a single registry
  (OpenAI, Anthropic, Google, Azure, AWS Bedrock, DeepSeek, SiliconFlow,
  Qwen, Zhipu, Moonshot, Yi, Baichuan, Doubao, StepFun, Ollama, vLLM,
  LM Studio, and the offline placeholder).

## [0.1.0] - 2025-05-29

### Added
- Initial release of the DATA-AI CLI
- Multi-model support (OpenAI, Anthropic, Google, Azure, AWS, Ollama)
- ReAct Agent implementation
- Tool-Call Agent mode
- 60+ built-in tools
- RAG system with multiple vector stores
- Memory system with session and semantic memory
- Plugin system architecture
- Docker sandbox support
- Daytona cloud sandbox integration
- Office document processing (Word, Excel, PPT, PDF)
- Browser automation
- Data analysis capabilities
- CLI interface with rich UI
- Configuration system with TOML support
- Test suite
- Documentation

[Unreleased]: https://github.com/badhope/DATA-AI/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/badhope/DATA-AI/compare/v0.1.0...v2.0.0
[0.1.0]: https://github.com/badhope/DATA-AI/releases/tag/v0.1.0
