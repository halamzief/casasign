# CasaSign

Generic digital document signature service with audit trails, multi-signer support, and email notifications.

**Production**: Deployed via Dokploy, domain `sign.signcasa.de`

## Features

- **Multi-signer** sequential or parallel signing with configurable order
- **Magic links** — signers click a link, no account needed
- **Canvas signatures** — mobile-optimized touch signature pad
- **Three document modes** — HTML (recommended), JSON (key-value), PDF (legacy)
- **Audit trail** — IP, user agent, geolocation, timestamps per action
- **Email notifications** — template-based via Resend (Jinja2 rendering)
- **Multi-tenant** — `tenant_id` isolation on all queries
- **Webhook callbacks** — notify caller on completion

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn (Python 3.12) |
| Database | PostgreSQL 16 + SQLAlchemy async (asyncpg) |
| Signing UI | Jinja2 + Alpine.js + htmx + Tailwind CSS |
| Email | Resend API |
| PDF | ReportLab + Playwright (HTML-to-PDF) |
| Deployment | Docker + Dokploy |

## Quick Start

```bash
uv sync --all-extras
cp .env.example .env   # Edit with your DB, Resend key, secret

uv run uvicorn src.main:app --reload --port 9000
# API docs: http://localhost:9000/docs
```

## API Reference

### Create Signature Request

```http
POST /api/sign/request
```

```json
{
  "contract_id": "550e8400-e29b-41d4-a716-446655440000",
  "requester_user_id": "uuid",
  "requester_email": "sender@example.com",
  "tenant_id": "uuid",

  "document_title": "Kaufvertrag Musterstr. 1",
  "document_html": "<div class='contract'>...your rendered HTML...</div>",
  "sender_name": "Max Mustermann",
  "document_name": "Kaufvertrag",

  "email_variables": {
    "property_address": "Musterstr. 1, 10115 Berlin",
    "custom_field": "passed to email template"
  },

  "signers": [
    {"name": "Alice Sender", "email": "alice@example.com", "role": "sender", "signing_order": 1},
    {"name": "Bob Recipient", "email": "bob@example.com", "role": "recipient", "signing_order": 2}
  ],

  "expires_in_days": 30,
  "callback_url": "https://yourapp.com/api/webhooks/signature"
}
```

### Check Status

```http
GET /api/sign/status/{request_id}
```

Returns: `status` (pending/in_progress/completed/expired), `signed_count`, `pending_signers`, `expires_at`.

### Validate Signing Token

```http
GET /api/sign/{token}
```

Called when signer clicks the magic link. Returns document HTML, signer info, and metadata.

### Complete Signature

```http
POST /api/sign/{token}/complete
```

Submits signature image (base64 PNG) + consent data. Triggers next signer notification or completion.

### Download Signed PDF

```http
GET /api/sign/download/{request_id}/file
```

Returns the signed PDF with embedded signatures and audit trail.

## Signing Flow

```
Caller creates request → CasaSign sends email to signer 1
    ↓
Signer 1 clicks magic link → views document → signs on canvas
    ↓
CasaSign sends email to signer 2 (sequential)
    ↓
Signer 2 signs → status = "completed" → webhook fired
    ↓
Caller downloads signed PDF via /download endpoint
```

## Document Modes

| Mode | Field | When to Use |
|------|-------|-------------|
| **HTML** | `document_html` | Caller renders document HTML (recommended) |
| **JSON** | `contract_data` | CasaSign renders key-value view from dict |
| **PDF** | `document_pdf_base64` | Upload pre-built PDF (legacy) |

**Recommended**: Use HTML mode. Your app renders the document however it wants, CasaSign just displays and collects signatures.

## Email Templates

Stored in `email_templates` database table. Rendered with Jinja2.

**Required templates:**

| Key | Purpose | Default Variables |
|-----|---------|------------------|
| `signature_request` | Sent to signers with signing link | `signer_name`, `signing_link`, `sender_name`, `document_title` + `email_variables` |
| `signature_completed` | Sent when all parties signed | `recipient_name`, `download_link` |
| `signature_reminder` | Reminder for pending signers | `signer_name`, `signing_link`, `expires_at` |

Custom variables from `email_variables` are merged into all templates.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | **required** | `postgresql+asyncpg://...` |
| `RESEND_API_KEY` | **required** | Resend email API key |
| `SECRET_KEY` | **required** | App secret for token signing |
| `SERVICE_NAME` | `casasign` | Service name (branding) |
| `FROM_EMAIL` | `signatures@casasign.dev` | Email sender address |
| `FROM_NAME` | `CasaSign` | Email sender display name |
| `SIGNING_BASE_URL` | `https://sign.casasign.dev` | Base URL for signing links |
| `SIGNATURE_EXPIRY_DAYS` | `7` | Default link expiry |
| `ALLOWED_ORIGINS` | `localhost` | CORS allowed origins |
| `SIGNATURES_STORAGE_PATH` | `./storage/signatures` | PDF file storage |

## Development

```bash
uv run ruff check src/ --fix && uv run ruff format src/
uv run mypy src/
uv run pytest tests/ -v
```

## Deployment

Docker build with Playwright for HTML-to-PDF:

```bash
docker build -t casasign .
docker run -p 9001:9001 --env-file .env casasign
```

Health check: `GET /health`

## Using with Other Services

CasaSign is document-type agnostic. Any service can use it:

```python
# Your app renders the document HTML however it wants
document_html = render_my_contract(contract_data)

# Send to CasaSign
response = httpx.post("http://casasign:9001/api/sign/request", json={
    "contract_id": str(contract.id),
    "document_title": "Mietvertrag Musterstr. 1",
    "document_html": document_html,
    "sender_name": "Max Mustermann",
    "signers": [{"name": "Bob", "email": "bob@example.com", "role": "tenant", "signing_order": 1}],
    "requester_user_id": str(user.id),
    "requester_email": user.email,
    "tenant_id": str(tenant.id),
})
```
