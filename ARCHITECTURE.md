# Architecture

## Overview

CasaSign is a standalone digital signature microservice. It accepts documents (HTML, JSON, or PDF), sends signing invitations via email, captures canvas signatures, and produces signed PDFs with audit trails.

It is document-type agnostic — the caller controls what the document looks like.

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Caller (e.g. SignCasa)                 │
│  POST /api/sign/request with document_html + signers     │
└────────────────────────┬─────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│                      CasaSign API                        │
│  ┌──────────┐ ┌────────────┐ ┌────────────┐             │
│  │Signatures│ │   Pages    │ │   Admin    │              │
│  │  (REST)  │ │ (Jinja2)   │ │ Templates  │              │
│  └────┬─────┘ └─────┬──────┘ └────────────┘              │
│       └─────────────┴──────────────┘                     │
│  ┌───────────────────────────────────────────────────┐   │
│  │              Service Layer                         │   │
│  │  SignatureRequestService  │  SigningService         │   │
│  │  CompletionService        │  AuditService           │   │
│  └───────────────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────────────┐   │
│  │              Infrastructure                        │   │
│  │  SignatureRepository │ EmailService │ PDFProcessor  │   │
│  └───────────────────────────────────────────────────┘   │
└────────────────────────┬─────────────────────────────────┘
                         ↓
          ┌──────────────┴──────────────┐
          ↓                              ↓
   ┌──────────────┐             ┌──────────────┐
   │ PostgreSQL   │             │   Resend     │
   │  4 tables    │             │  (Email)     │
   └──────────────┘             └──────────────┘
```

## Module Structure

```
src/
├── api/                        # FastAPI routes
│   ├── signatures.py           # REST API: create, status, complete, download
│   ├── pages.py                # Jinja2 pages: /sign/{token}, /sign/{token}/success
│   ├── admin_templates.py      # CRUD for email templates
│   └── sse_status.py           # Server-sent events for real-time status
├── config.py                   # Pydantic Settings (env vars)
├── main.py                     # FastAPI app, middleware, lifespan
├── core/
│   ├── services/
│   │   ├── signature_request_service.py  # Create request, send first email
│   │   ├── signing_service.py            # Token validation, signature capture
│   │   └── completion_service.py         # PDF generation, webhook, audit
│   ├── email/
│   │   ├── resend_service.py             # Generic send_email() via Resend
│   │   └── template_service.py           # Jinja2 template rendering from DB
│   ├── pdf/
│   │   ├── pdf_processor.py              # PDF manipulation (embed signatures)
│   │   ├── html_to_pdf_service.py        # Playwright HTML→PDF conversion
│   │   └── audit_trail_generator.py      # Append audit page to PDF
│   ├── audit/
│   │   └── audit_service.py              # Event logging to signature_audit_log
│   └── repositories/
│       ├── signature_repository.py       # CRUD for requests + signers
│       └── email_template_repository.py  # CRUD for email templates
├── database/
│   ├── engine.py               # SQLAlchemy async engine
│   ├── session.py              # Session factory + dependency
│   ├── base.py                 # Declarative base
│   └── models/
│       ├── signature_request.py  # SignatureRequestRow, SignatureSignerRow
│       ├── email_template.py     # EmailTemplateRow
│       └── audit_log.py          # SignatureAuditLogRow
├── models/                     # Domain models (not ORM)
│   ├── signature_request.py    # SignatureRequest, SignatureSigner, SignatureAuditLog
│   └── email_template.py       # EmailTemplate
├── schemas/                    # Pydantic request/response schemas
│   ├── signature.py            # SignatureRequestCreate, SignerCreate, responses
│   ├── signing.py              # TokenValidationResponse, ConsentSubmission
│   └── email.py                # EmailSendResponse, EmailTemplateCreate
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Base layout (Alpine.js + Tailwind CDN)
│   ├── sign/
│   │   ├── signing_page.html   # Document view + signature pad
│   │   └── success_page.html   # Post-signing confirmation
│   ├── partials/
│   │   ├── consent_modal.html  # Identity + document review consent
│   │   ├── contract_viewer.html
│   │   └── contract_preview.html
│   ├── contract_final.html     # PDF template wrapper
│   └── static/js/
│       ├── signature-pad.js    # Canvas signature component
│       └── signing-flow.js     # Consent modal Alpine.js data
└── utils/
    ├── token_generator.py      # Cryptographic verification tokens
    └── hash_utils.py           # SHA-256 document hashing
```

## Database Schema

### 4 Tables

```sql
signature_requests       -- Core signing requests
├── id (UUID PK)
├── contract_id (UUID)   -- Caller's document ID
├── tenant_id (UUID)     -- Multi-tenant isolation
├── requester_user_id, requester_email
├── document_type        -- 'pdf', 'json', 'html'
├── document_html (TEXT) -- Pre-rendered HTML from caller
├── document_title       -- Display title
├── sender_name          -- Who sent it
├── contract_data (JSON) -- Raw data (JSON mode)
├── email_variables (JSON) -- Custom email template vars
├── document_name        -- For PDF filename
├── document_hash, document_url -- PDF mode
├── status               -- pending → in_progress → completed
├── expires_at, created_at, completed_at
├── callback_url         -- Webhook on completion
└── custom_email_template_id

signature_signers        -- Per-signer tracking
├── id (UUID PK)
├── request_id (FK → signature_requests)
├── name, email, phone, role
├── signing_order        -- Sequential signing
├── verification_token   -- Magic link token (unique)
├── verification_method  -- email_link / whatsapp_link
├── signed_at, ip_address, user_agent, geolocation
└── signature_image_base64 -- Canvas signature PNG

email_templates          -- Customizable email templates
├── id (UUID PK)
├── tenant_id            -- Per-tenant customization
├── template_key         -- signature_request, signature_completed, etc.
├── subject_template, body_html, body_text -- Jinja2 templates
├── language, is_default, is_active
└── created_at, updated_at

signature_audit_log      -- Immutable audit trail
├── id (UUID PK)
├── request_id (FK)
├── event_type           -- request_created, email_sent, link_clicked, signed, etc.
├── actor_email, actor_role
├── ip_address, user_agent
├── metadata (JSON)
└── created_at
```

## Key Data Flows

### 1. Create Signature Request

```
Caller POST /api/sign/request
  → SignatureRequestService.create_signature_request()
    → SignatureRepository.create_request() (DB insert)
    → Generate verification_token per signer
    → Send email to first signer(s) via ResendEmailService
  → Return request_id + signer details
```

### 2. Signer Opens Link

```
Signer clicks email link → GET /sign/{token}
  → Pages router renders signing_page.html
  → JS fetches GET /api/sign/{token}
    → SigningService.validate_token_and_get_contract()
      → Look up signer by token
      → Check expiry (timezone-aware)
      → Log link_clicked audit event
      → Return document_html + signer info
  → Display consent modal → document → signature pad
```

### 3. Signer Submits Signature

```
POST /api/sign/{token}/complete
  → SigningService.complete_signature()
    → Store signature_image_base64, ip, user_agent
    → Log consent + signed audit events
    → Check if all signers done:
      Yes → status = "completed", fire webhook
      No  → status = "in_progress", email next signer
```

### 4. PDF Generation (on completion)

```
POST /api/sign/process-completed/{request_id}
  → CompletionService.process_completed_request()
    → HTMLToPDFService: render document_html → PDF via Playwright
    → PDFProcessor: embed signature images into PDF
    → AuditTrailGenerator: append audit page
    → Save final signed PDF to storage
```

## Security

- **Verification tokens**: 64-char cryptographically random strings
- **Document hashing**: SHA-256 integrity check (PDF mode)
- **CORS**: Configurable allowed origins
- **Audit trail**: Every action logged with IP, user agent, timestamp
- **Multi-tenant**: `tenant_id` on all queries
- **No auth on signing pages**: Magic links are the auth (token = access)

## Configuration

All settings via environment variables (Pydantic Settings):

| Category | Variables |
|----------|----------|
| Core | `DATABASE_URL`, `SECRET_KEY`, `SERVICE_PORT` |
| Email | `RESEND_API_KEY`, `FROM_EMAIL`, `FROM_NAME` |
| Signing | `SIGNING_BASE_URL`, `SIGNATURE_EXPIRY_DAYS` |
| Branding | `SERVICE_NAME` (affects API title, health check) |
| Storage | `SIGNATURES_STORAGE_PATH`, `MAX_PDF_SIZE_MB` |
| Security | `ALLOWED_ORIGINS` |

## Integration Pattern

CasaSign is designed as a shared microservice. Callers are responsible for:

1. **Rendering the document** — pass `document_html` (CasaSign doesn't know your document structure)
2. **Building email variables** — pass `email_variables` dict for template rendering
3. **Listening for completion** — via `callback_url` webhook or polling `/api/sign/status/{id}`

This keeps CasaSign document-type agnostic — it works for rental contracts, NDAs, purchase agreements, or any document that needs signatures.
