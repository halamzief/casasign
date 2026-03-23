# Week 4 Progress: Main App Integration

**Date**: 2025-11-23
**Session**: 021
**Status**: 🚧 In Progress

---

## Objective

Integrate the FES Signature Microservice with the main SignCasa application to replace eSignatures.com dependency.

**Goals**:
1. ✅ Analyze current eSignatures.com integration
2. ✅ Create FES client wrapper for main app
3. 🚧 Update SignatureService to use FES microservice
4. ⏳ Update webhook handlers to receive FES callbacks
5. ⏳ Build email template admin UI
6. ⏳ Mobile optimization
7. ⏳ Write E2E tests with Playwright
8. ⏳ Production deployment

---

## Completed Tasks

### 1. Analysis of Current eSignatures.com Integration ✅

**Files Analyzed**:
- `src/core/contracts/signature/service.py` - High-level signature service
- `src/core/contracts/signature/api_client.py` - eSignatures.com HTTP client
- `src/api/webhooks.py` - Webhook event handler
- `src/api/contracts/documents.py` - Contract signing API

**Current Architecture**:
```
SignatureService (high-level)
    ↓
eSignaturesAPI (HTTP client)
    ↓
eSignatures.com API (external SaaS)
    ↓
Webhook callback → /api/v1/webhooks/esignatures
```

**Key Methods**:
- `initiate_contract_signing()` - Create signature request via template
- `check_signature_status()` - Poll for status updates
- `download_signed_contract()` - Download final PDF
- `cancel_signature_request()` - Cancel ongoing request
- `send_signing_reminder()` - Send reminder to signer

**Webhook Events**:
- `contract-signed` - All signers complete
- `signer-signed` - Individual signer completes
- `signer-declined` - Signer declines
- `contract-withdrawn` - Request cancelled/expired

---

### 2. FES Client Wrapper Created ✅

**File**: `src/core/contracts/signature/fes_client.py` (460 lines)

**Classes**:
1. `FESSignatureAPI` (async) - Modern async/await HTTP client
2. `FESSignatureAPISync` (sync) - Backward-compatible synchronous wrapper

**Key Features**:
- **eSignatures.com-compatible interface** - Drop-in replacement
- **Automatic format conversion** - Signers, roles, verification methods
- **Async HTTP client** (httpx) - Fast, modern networking
- **Sync wrapper** - Works with existing sync code
- **Environment config** - `FES_SIGNATURE_SERVICE_URL` env var

**Methods**:
- `create_signature_request(document_data, request)` - Create request
- `get_signature_status(request_id)` - Get current status
- `cancel_signature_request(request_id)` - Cancel request (stub)
- `download_signed_document(request_id)` - Download final PDF
- `send_reminder(request_id, signer_email)` - Send reminder (stub)

**Role Mapping**:
```python
{
    "landlord": "landlord",
    "tenant": "tenant_1",
    "tenant_1": "tenant_1",
    "tenant_2": "tenant_2",
}
```

**Verification Method Mapping**:
```python
{
    ["email"]: "email_magic_link",
    ["sms"]: "whatsapp_link",
    ["whatsapp"]: "whatsapp_link",
}
```

---

### 3. FES Microservice PDF Download Endpoint Added ✅

**File**: `signcasa-signatures/src/api/signatures.py`

**New Endpoint**: `GET /api/sign/download/{request_id}/file`

**Purpose**: Return actual PDF file bytes (not just metadata)

**Response**:
- Media type: `application/pdf`
- Filename: `Mietvertrag_{contract_id}_signed.pdf`
- Uses FastAPI `FileResponse` for efficient file serving

**Example**:
```bash
curl -O http://localhost:9000/api/sign/download/uuid/file
# Downloads: Mietvertrag_uuid_signed.pdf
```

---

### 4. SignatureService Updated with Feature Flag 🚧

**File**: `src/core/contracts/signature/service.py`

**Changes**:
1. **Import FES client**:
   ```python
   from .fes_client import FESSignatureAPISync
   ```

2. **Constructor accepts `use_fes` flag**:
   ```python
   def __init__(self, db_session, use_fes: bool = None):
       if use_fes is None:
           use_fes = os.getenv("USE_FES_SIGNATURE_SERVICE", "false").lower() == "true"
       self.use_fes = use_fes
       self.api_client = self._initialize_api_client()
   ```

3. **Dynamic client initialization**:
   ```python
   def _initialize_api_client(self) -> eSignaturesAPI | FESSignatureAPISync:
       if self.use_fes:
           fes_url = os.getenv("FES_SIGNATURE_SERVICE_URL", "http://localhost:9000")
           return FESSignatureAPISync(base_url=fes_url)
       else:
           # eSignatures.com (legacy)
           ...
   ```

**Environment Variables**:
- `USE_FES_SIGNATURE_SERVICE=true` - Enable FES microservice
- `FES_SIGNATURE_SERVICE_URL=http://localhost:9000` - FES base URL

**Backward Compatibility**:
- Default: `false` (uses eSignatures.com)
- No code changes required in API layer
- Gradual migration supported (toggle per-tenant if needed)

---

## In Progress

### 5. Webhook Handler Update ⏳

**Current**: `/api/v1/webhooks/esignatures` receives eSignatures.com callbacks

**Needed**: Support FES callback format

**FES Webhook Payload** (from WEEK3_COMPLETE.md):
```json
{
  "event": "signature_completed",
  "request_id": "uuid",
  "contract_id": "uuid",
  "signed_pdf_path": "/storage/signatures/contract_uuid_request_uuid_signed.pdf",
  "signed_pdf_url": "http://localhost:9000/api/sign/download/request_uuid",
  "completed_at": "2025-11-23T15:30:00Z",
  "signers": [
    {
      "name": "Max Müller",
      "email": "max@example.com",
      "role": "tenant_1",
      "signed_at": "2025-11-23T15:25:00Z",
      "ip_address": "192.168.1.100"
    }
  ]
}
```

**Action Items**:
- [ ] Add `/api/v1/webhooks/fes-signatures` endpoint
- [ ] Map FES events to ContractStatus updates
- [ ] Download PDF via FES client
- [ ] Store PDF with same logic as eSignatures
- [ ] Log audit trail

---

## Pending Tasks

### 6. Email Template Admin UI ⏳

**Goal**: `/admin/signature-templates` page for editing email templates

**Features Needed**:
- List all email templates (signature request, reminder, completion)
- Live preview with sample data
- Template editor with Jinja2 syntax highlighting
- Test email sending
- Version history

**Tables** (already exist in FES):
- `email_templates` - Template storage
- `EmailTemplateRepository` - Data access
- `EmailTemplateService` - Business logic

---

### 7. Mobile Optimization ⏳

**Target**: Signing page (`/sign/{token}`) mobile-friendly

**Requirements**:
- Responsive canvas signature pad
- Touch-optimized consent checkboxes
- Readable contract text on small screens
- Fast loading (lazy load components)

---

### 8. E2E Tests with Playwright ⏳

**Goal**: Full integration tests

**Scenarios**:
1. Create contract in main app
2. Send for signature via FES
3. First signer receives email
4. First signer signs contract
5. Second signer receives email
6. Second signer signs contract
7. Webhook triggers PDF processing
8. Main app receives callback
9. PDF downloaded and stored
10. Contract status updated to "completed"

---

### 9. Production Deployment ⏳

**Requirements**:
- Docker Compose setup for FES microservice
- SSL certificate for `sign.signcasa.de` subdomain
- Reverse proxy configuration (Caddy/nginx)
- Environment variables for production
- Database migration scripts
- Health check endpoints
- Monitoring and logging

---

## Technical Decisions

### Decision 1: Feature Flag for Gradual Migration

**Context**: Main app currently uses eSignatures.com, need to migrate to FES

**Decision**: Use environment variable `USE_FES_SIGNATURE_SERVICE` for toggle

**Rationale**:
- ✅ Zero downtime migration (test FES with subset of users)
- ✅ Easy rollback if issues occur
- ✅ No code changes in API layer
- ✅ Can migrate tenant-by-tenant if needed

**Implementation**:
```bash
# Development: Test FES
USE_FES_SIGNATURE_SERVICE=true

# Production: Keep eSignatures until ready
USE_FES_SIGNATURE_SERVICE=false
```

---

### Decision 2: Sync Wrapper for FES Client

**Context**: Main app uses synchronous code, FES client is async

**Decision**: Created `FESSignatureAPISync` wrapper with event loop management

**Rationale**:
- ✅ No need to refactor all API endpoints to async
- ✅ Backward compatible with existing code
- ✅ Can migrate to async later incrementally
- ❌ Slight performance overhead (event loop creation)

**Alternative Considered**: Refactor entire API to async (rejected - too risky)

---

### Decision 3: eSignatures.com-Compatible Interface

**Context**: FES microservice uses different payload format than eSignatures

**Decision**: FES client converts formats internally, exposes same interface

**Rationale**:
- ✅ Drop-in replacement - minimal code changes
- ✅ All conversion logic in one place
- ✅ Easy to test and debug
- ❌ Slightly more complex client code

**Example**:
```python
# SignatureService code stays the same
signature_request = SignatureRequest(...)
response = self.api_client.create_signature_request(None, signature_request)

# FES client converts internally:
# SignatureRequest → FES payload → HTTP POST → Convert response back
```

---

## Next Steps

**Immediate (Next Hour)**:
1. Update webhook handler to support FES callbacks
2. Test end-to-end flow with FES enabled
3. Document PDF generation requirement for FES

**Short Term (This Session)**:
4. Build email template admin UI (basic CRUD)
5. Mobile responsive testing
6. Write E2E test scenarios

**Long Term (Next Session)**:
7. Production deployment setup
8. SSL certificates
9. Performance testing
10. Migration documentation

---

## Files Modified

### Main App
| File | Lines Changed | Purpose |
|------|---------------|---------|
| `src/core/contracts/signature/service.py` | ~30 | Add FES support with feature flag |
| `src/core/contracts/signature/fes_client.py` | +460 (new) | FES HTTP client wrapper |

### FES Microservice
| File | Lines Changed | Purpose |
|------|---------------|---------|
| `signcasa-signatures/src/api/signatures.py` | +60 | Add PDF file download endpoint |

**Total New Code**: ~520 lines

---

## Testing Status

### Manual Testing ⏳
- [ ] Enable FES via env var
- [ ] Create signature request via main app
- [ ] Verify FES receives request
- [ ] Complete signatures in FES UI
- [ ] Verify webhook callback
- [ ] Verify PDF download
- [ ] Verify contract status update

### Unit Tests ⏳
- [ ] `test_fes_client.py` - FES client methods
- [ ] `test_signature_service_fes.py` - Service with FES enabled
- [ ] `test_webhook_fes.py` - FES webhook handling

### Integration Tests ⏳
- [ ] `test_contract_signing_e2e.py` - Full flow with FES

---

## Notes

**PDF Generation**: FES requires actual PDF bytes (not templates). Current main app uses eSignatures.com templates, which don't generate local PDFs. Options:

1. **Generate PDF before signing** - Use ReportLab to create contract PDF, then send to FES
2. **FES template support** - Add template rendering to FES microservice (future)
3. **Hybrid approach** - Use eSignatures templates temporarily, migrate to FES templates later

**Recommendation**: Option 1 - Generate PDF before signing (cleaner architecture, full control)

---

## Related Documents

- [WEEK1_COMPLETE.md](WEEK1_COMPLETE.md) - FES backend foundation
- [WEEK2_COMPLETE.md](WEEK2_COMPLETE.md) - FES signing UI
- [WEEK3_COMPLETE.md](WEEK3_COMPLETE.md) - PDF processing + webhooks
- [SSE_IMPLEMENTATION.md](SSE_IMPLEMENTATION.md) - Real-time status updates

---

**Week 4 Status**: 🚧 **35% Complete** - Core integration infrastructure ready, webhook + UI work remaining
