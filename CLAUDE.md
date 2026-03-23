# CLAUDE.md - signcasa-signatures

## Project Overview

FES (Fortgeschrittene Elektronische Signatur) compliant digital signature microservice for German rental contracts.

## Quick Start

```bash
uv sync --all-extras
uv run uvicorn src.main:app --reload --port 9000
```

## Tech Stack

- **Backend:** FastAPI (Python 3.12)
- **Templates:** Jinja2 + htmx + Alpine.js
- **Database:** PostgreSQL
- **Email:** Resend
- **Package Manager:** UV

## Key Commands

```bash
# Development
uv run uvicorn src.main:app --reload --port 9000

# Testing
uv run pytest tests/ -v
uv run pytest --cov=src --cov-report=html

# Code Quality
uv run ruff check src/ --fix
uv run ruff format src/
uv run mypy src/
```

## Project Structure

```
src/
├── api/           # FastAPI routes
│   └── pages.py   # Template rendering routes
├── core/          # Business logic
│   ├── email/     # Email templates & sending
│   ├── pdf/       # PDF processing & signing
│   └── auth/      # Token validation
├── models/        # Database models
└── schemas/       # Pydantic schemas
templates/
├── base.html      # Base template (Tailwind/htmx/Alpine CDN)
├── sign/          # Signing flow pages
└── partials/      # Reusable components
static/
└── js/            # Vanilla JS modules
```

## Documentation

- **TASKS.md** - Current tasks and backlog
- **CHANGELOG.md** - Session summaries
- **docs/sessions/** - Detailed session logs

## API Endpoints

- `POST /api/sign/request` - Create signature request
- `GET /api/sign/{token}` - View contract (renders signing page)
- `POST /api/sign/complete` - Submit signature
- `GET /api/sign/status/{request_id}` - Check status
