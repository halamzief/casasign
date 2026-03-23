# CasaSign

Generic digital document signature service with audit trails, multi-signer support, and email notifications.

## Features

- Multi-signer document signing with sequential or parallel signing order
- Token-based magic links for signers (no account required)
- Canvas signature capture (mobile-optimized)
- Audit trail with IP, user agent, geolocation, and timestamps
- Template-based email notifications via Resend
- PDF and HTML document modes
- Multi-tenant isolation via `tenant_id`
- Webhook callbacks on completion

## Stack

- **Backend**: FastAPI + SQLAlchemy async (PostgreSQL)
- **Frontend**: Jinja2 + Alpine.js + htmx + Tailwind CSS
- **Email**: Resend
- **PDF**: ReportLab + Playwright (HTML-to-PDF)

## Quick Start

```bash
uv sync --all-extras
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/casasign"
export RESEND_API_KEY="re_xxx"
export SECRET_KEY="your-secret-key"
uv run uvicorn src.main:app --reload --port 9000
```

## API

### Create Signature Request

```bash
POST /api/sign/request
```

```json
{
  "contract_id": "uuid",
  "requester_user_id": "uuid",
  "requester_email": "sender@example.com",
  "tenant_id": "uuid",
  "document_title": "Mietvertrag Musterstr. 1",
  "document_html": "<div>Your pre-rendered document HTML</div>",
  "sender_name": "Max Mustermann",
  "email_variables": {
    "property_address": "Musterstr. 1, 10115 Berlin"
  },
  "signers": [
    {"name": "Alice", "email": "alice@example.com", "role": "sender", "signing_order": 1},
    {"name": "Bob", "email": "bob@example.com", "role": "recipient", "signing_order": 2}
  ],
  "expires_in_days": 30
}
```

### Signing Flow

1. Signer receives email with magic link
2. `GET /sign/{token}` renders signing page with document
3. Signer reviews, confirms identity, signs on canvas
4. `POST /api/sign/{token}/complete` submits signature
5. Next signer notified (sequential signing)
6. All signed: status -> `completed`, webhook fired

## Document Modes

| Mode | Field | Use Case |
|------|-------|----------|
| **HTML** | `document_html` | Pre-rendered HTML from caller (recommended) |
| **JSON** | `contract_data` | Raw JSON data, rendered as key-value view |
| **PDF** | `document_pdf_base64` | Legacy PDF upload |

## Email Templates

Stored in `email_templates` table, rendered with Jinja2. Required: `signature_request`, `signature_completed`, `signature_reminder`.

Default variables: `signer_name`, `signing_link`, `sender_name`, `document_title`. Additional from `email_variables`.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | required | PostgreSQL connection |
| `RESEND_API_KEY` | required | Resend API key |
| `SECRET_KEY` | required | App secret |
| `SERVICE_NAME` | `casasign` | Branding name |
| `FROM_EMAIL` | `signatures@casasign.dev` | Sender email |
| `SIGNING_BASE_URL` | `https://sign.casasign.dev` | Signing link base URL |
