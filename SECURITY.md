# Security Policy

## Supported Versions

The following versions of `local-whisper` receive security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

We recommend always using the latest released version.

## Reporting a Vulnerability

We take security issues seriously. If you discover a security vulnerability, please report it responsibly.

**Please do NOT file a public GitHub issue for security vulnerabilities.**

Instead, please report it via one of:

1. **GitHub Security Advisories** (preferred):
   Go to the [Security Advisories](https://github.com/neromorph/local-whisper/security/advisories) tab and click "Report a vulnerability".

2. **Email**:
   Send details to the maintainer via GitHub's private vulnerability reporting.

When reporting, please include:

- Type of vulnerability (e.g., SSRF, injection, etc.)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact assessment — how the vulnerability affects the application

## Response Timeline

We aim to acknowledge vulnerability reports within **48 hours** and to provide a resolution timeline within **14 days**.

| Timeline | Commitment |
|----------|------------|
| Acknowledgement | Within 48 hours |
| Initial assessment | Within 7 days |
| Fix ready for release | Within 30 days (for critical issues) |
| Public disclosure | Coordinated with reporter |

## Security Best Practices for Deployers

When deploying `local-whisper`:

- **Network isolation** — The app binds to `127.0.0.1` by default. If exposing publicly, use a reverse proxy (nginx, Caddy) with TLS termination.
- **CORS** — Set `ALLOW_ORIGINS` to your exact frontend origin. Do not use `*` in production.
- **File size limits** — Adjust `MAX_UPLOAD_MB` based on your infrastructure's memory constraints.
- **URL mode SSRF protection** — The app blocks private IP ranges, localhost, and link-local addresses. Keep `yt-dlp` updated for upstream SSRF fixes.
- **Model cache** — The `MODEL_CACHE_DIR` and `TEMP_DIR` should be on a filesystem with appropriate access controls.
- **Secret scanning** — Enable GitHub Secret Scanning on your repository to prevent accidental secret commits.

## Security Scanning

This project runs automated security scans on every PR and release:

- **pip-audit** — Scans Python dependencies for known vulnerabilities
- **Bandit** — Static analysis for common Python security issues
- **Trivy** — Scans Docker images for OS-level vulnerabilities
- **Dependabot** — Automated dependency updates with security alerts

We strive to address disclosed vulnerabilities promptly and release patches as patches as quickly as possible.
