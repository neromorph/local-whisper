# Contributing to local-whisper

Thank you for considering a contribution! This document outlines everything you need to know to get started.

## Quick Start

```bash
# 1. Fork and clone the repo
git clone https://github.com/YOUR_USERNAME/local-whisper.git
cd local-whisper

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dev dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Install pre-commit hooks
pre-commit install --install-hooks

# 5. Run the test suite
pytest -v

# 6. Create a feature branch
git checkout -b feat/your-feature-name
```

## Development Workflow

### Branch Naming

Use descriptive branch names with type prefixes:

| Prefix | Use case |
|--------|----------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring (no behavior change) |
| `test/` | Adding or updating tests |
| `chore/` | Maintenance tasks (deps, CI, config) |
| `security/` | Security-related changes |

Examples:
```bash
git checkout -b feat/url-batch-transcription
git checkout -b fix/oversized-file-crash
git checkout -b docs/update-readme-screenshots
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `security`
**Scope:** optional, e.g., `feat(routes):`, `fix(url-service):`

Examples:
```bash
git commit -m "feat(routes): add batch transcription endpoint"
git commit -m "fix(url-service): block private IP ranges in URL mode"
git commit -m "docs(readme): add Docker quick start section"
git commit -m "test: add integration tests for job cancellation"
```

### Code Style

This project uses modern Python tooling:

- **Black** — Code formatter (line length: 88)
- **isort** — Import sorter
- **ruff** — Linter (replaces flake8, pyupgrade, and more)
- **mypy** — Optional type checker

Run all formatters and linters before committing:

```bash
# Format + lint all files
ruff check --fix .
ruff format .

# Or via pre-commit (runs automatically before each commit)
pre-commit run --all-files
```

### Type Annotations

New code should use type annotations where practical:

```python
from typing import Any

def process_transcription(file_path: str, model: str) -> dict[str, Any]:
    ...
```

### Testing

All PRs must pass tests. Write tests for new features and bug fixes.

**Test structure:**
- `tests/test_routes.py` — API integration tests using `fastapi.testclient.TestClient`
- Tests use `pytest` with `pytest-asyncio` for async tests

**Running tests:**

```bash
# All tests
pytest -v

# With coverage
pytest --cov=app --cov-report=html --cov-report=term -v

# Specific test file
pytest tests/test_routes.py -v

# Specific test
pytest tests/test_routes.py::test_health_returns_expected_fields -v

# Watch mode (re-run on file change)
pytest --watch -v
```

**Test conventions:**
- Test function names: `test_<what_is_tested>`
- Use descriptive assertions: `assert response.status_code == 200, response.json()`
- Mock heavy operations (Whisper transcription) at the service boundary

## Project Architecture

### API Design

The app exposes a REST API. Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve frontend HTML |
| `GET` | `/health` | Health check |
| `GET` | `/extensions` | Allowed file extensions |
| `POST` | `/transcribe` | Upload + transcribe audio/video |
| `POST` | `/transcribe/url` | Start URL transcription job |
| `GET` | `/jobs/{job_id}/status` | Poll job status |
| `POST` | `/jobs/{job_id}/cancel` | Cancel a running job |

### Service Layer

```
app/
├── config.py         # Environment config (single source of truth)
├── routes.py         # HTTP layer (FastAPI router)
└── services/
    ├── whisper_service.py  # faster-whisper transcription
    ├── job_service.py      # Background job state machine
    └── url_service.py      # URL validation + yt-dlp
```

Keep business logic in `services/`. Routes should be thin wrappers around service calls.

## Pull Request Process

### PR Checklist

Before opening a PR, confirm:

- [ ] Branch is up to date with `main`
- [ ] Commit messages follow Conventional Commits
- [ ] Code passes all linters and formatters (`ruff check && ruff format`)
- [ ] All tests pass (`pytest -v`)
- [ ] New features have corresponding tests
- [ ] Bug fixes include a regression test
- [ ] Documentation updated if needed (README, GUIDE.md)
- [ ] No secrets or credentials in code
- [ ] Environment variables documented if added

### Opening the PR

Use the PR template (auto-populated from `.github/pull_request_template.md`).

### Review Process

PRs require at least one approval before merging. The maintainer may request changes for style, design, or correctness. Please be responsive to review feedback.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the maintainer.

## Questions?

Feel free to open a [Discussion](https://github.com/neromorph/local-whisper/discussions) for questions about the project, or open an issue for bugs and feature requests.
