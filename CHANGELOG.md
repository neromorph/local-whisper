# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Fixed

### Security

## [0.1.0] — 2026-04-29

### Added

- Initial public release
- FastAPI backend with `/health`, `/transcribe`, and `/transcribe/url` endpoints
- faster-whisper transcription engine with `tiny`, `base`, `small`, `medium`, and `turbo` models
- URL mode using yt-dlp for pulling audio from public media URLs
- Background job system with polling-based status checking and job cancellation
- Plain HTML/CSS/JS frontend with drag-and-drop file upload
- Model, language, and task (transcribe/translate) selection UI
- SRT subtitle export support
- Multi-stage Dockerfile for lean production image
- Docker Compose setup with optional NVIDIA GPU profile
- SSRF protection blocking private IP ranges and localhost in URL mode
- Pre-commit hooks (ruff, black, isort, pre-commit-hooks)
- pytest integration with TestClient-based API tests
- Automated CI pipeline via GitHub Actions
- Automated Docker image publishing to GHCR
- Security scanning with pip-audit, bandit, and Trivy
- Dependabot for automated dependency updates
- MIT License
- Contributor Covenant Code of Conduct
- SECURITY.md with vulnerability reporting policy

### Known Limitations

- `large` and `large-v3` Whisper models are not exposed in the UI to protect disk storage
- Transcription progress reporting is estimated; word-level progress is not yet available
- No batch transcription in this release (single file at a time)

[unreleased]: https://github.com/neromorph/local-whisper/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/neromorph/local-whisper/releases/tag/v0.1.0
