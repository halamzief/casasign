# Changelog

All notable changes to signcasa-signatures are documented here.

## [Session 086] - 2026-03-24

### Success Page Makeover, Typed Signatures, Consent Storage

Major UX improvements: success page redesigned as moving checklist, dual-mode signature pad (draw + type), and consent capture with full backend storage.

**Success Page Total Makeover (`templates/sign/success_page.html`):**
- Redesigned from ad-like page to smart moving checklist
- Clean hero with checkmark icon, structured next-steps checklist
- Strom/Gas card: "Grundversorgung ist bis zu 40% teurer" (explains why)
- Internet card: "Schaltung dauert oft 2-4 Wochen" (urgency through real info)
- Ummeldung as info banner, Umzug + Haftpflicht as secondary cards
- All umlauts fixed, removed fake email-send form

**Dual-Mode Signature Pad (`static/js/signature-pad.js`):**
- Draw tab: existing canvas drawing (unchanged behavior)
- Type tab: text input + 3 handwriting fonts (Caveat, Dancing Script, Pacifico)
- Font selector with visual preview, auto-size text to fit canvas
- Both modes produce identical base64 PNG for the API
- Fixed "Loschen" -> "Loschen" umlaut

**Consent Capture + Storage:**
- Optional service consents (energy, internet) below required consents in `partials/consent_inline.html`
- Wired energySignupConsent and internetSignupConsent into submit payload (`signing_page.html`)
- New `consents` JSONB column on `signature_signers` table (migration 006)
- Updated SignatureSignerRow model, SignatureSigner domain model, repository mapper
- `mark_signer_signed()` now stores consents
- `complete_signature()` passes consents through via `model_dump()`

**Success Page Data Fix (`api/pages.py`):**
- Fixed bug: was calling `.get()` on model object (always failed silently in try/except)
- Now reads `signer.consents`, extracts property address from contract_data
- Extracts move_in_date from `contract_data.mietzeit.mietbeginn`

**New Files:**
- `migrations/006_add_signer_consents.sql`

**Files Changed:**
- `src/templates/sign/success_page.html` (total rewrite)
- `src/templates/sign/signing_page.html` (consent state + submit payload)
- `src/templates/partials/consent_inline.html` (optional service consents)
- `src/templates/static/js/signature-pad.js` (dual-mode: draw + type)
- `src/database/models/signature_request.py` (consents JSONB column)
- `src/models/signature_request.py` (consents field on domain model)
- `src/core/repositories/signature_repository.py` (consents in mark_signer_signed)
- `src/core/services/signing_service.py` (pass consents to repo)
- `src/api/pages.py` (fix success page data extraction)

---

## [Session 084] - 2026-03-24

### CasaSign Section Extraction + Test Fixes

Completed full section default extraction: 16 section partials, dynamic include rendering, section-driven contract_final.html. Fixed pre-existing test failures.

**Section Partials (16 files):**
- Created `src/templates/partials/sections/section_{vermieter,mieter,mietobjekt,...,unterschriften}.html`
- Each partial extracted from monolithic `contract_clauses_1..4.html` files
- Dynamic include via `contract_section_renderer.html`

**Test Fixes:**
- Fixed regex mismatches in `test_json_mode.py` (Pydantic v2 error messages)
- 19 new section rendering tests
- 48/48 tests passing

---

## [Session 083] - 2026-03-24

### CasaSign: Attachment + Section Support

Implemented CasaSign-side support for contract attachments and clause section overrides, enabling SignCasa to send rich signing payloads with custom clauses and PDF attachments.

**Schema + Database:**
- AttachmentSchema + SectionSchema with nh3 HTML sanitization on SignatureRequestCreate
- `attachments` JSONB column on signature_requests + migration 005

**Processing Pipeline:**
- Store attachments to disk, merge sections into contract_data (repository + service)
- Include PDF attachments in signing invitation emails via Resend SDK
- Section-driven rendering with override support (contract_section_renderer.html)
- Section override support in contract_final.html (PDF template)
- Merge attachment PDFs into final signed document using pypdf

**Tests:**
- 14 schema validation tests for attachments and sections

**Commits:**
- test: add attachment and section schema validation tests (61cf1be)
- feat: merge attachment PDFs into final signed document (5dfa1b5)
- feat: add section override support to PDF template (1b0861b)
- feat: add section-driven rendering with override support (31eea3a)
- feat: include PDF attachments in signing invitation emails (0ccc6bd)
- feat: store attachments on disk and sections in contract_data (dbdbb24)
- feat: add attachments JSONB column to signature_requests (3e5ff19)
- feat: add attachment and section schemas to signing request (2fa6687)

**New Files:**
- `migrations/005_add_attachments_column.sql`
- `src/templates/partials/contract_section_renderer.html`
- `tests/test_attachments.py`
- `tests/test_sections.py`

**Stats:** 14 new tests, 15 files changed, 364 lines added

---

## [Session 049] - 2025-12-31

### FES Migration Phase 7-8: Jinja2 + Vanilla JS

**Phase 7 - FES Jinja2 Migration:**
- Created base template with Tailwind/htmx/Alpine.js CDN
- Converted SignaturePad.svelte (250 LOC) to vanilla JS class
- Converted ConsentModal.svelte (335 LOC) to Alpine.js x-data component
- Converted ContractPreview.svelte (467 LOC) to Jinja2 macros
- Created signing page template with full orchestration
- Created success page with affiliate links

**Phase 8 - SvelteKit Deletion:**
- Removed signcasa-signatures/frontend/ SvelteKit directory
- Removed frontend service from docker-compose.yml

**Files Created (10):**
- templates/base.html - Base template
- templates/sign/signing_page.html - Main signing page
- templates/sign/success_page.html - Success page
- templates/partials/consent_modal.html - Consent component
- templates/partials/contract_preview.html - JSON mode contract
- templates/partials/contract_viewer.html - PDF mode contract
- templates/partials/kaution_upsell.html - Deposit upsell
- static/js/signature-pad.js - Signature capture
- static/js/consent-modal.js - Consent logic
- src/api/pages.py - FastAPI template routes

## [Session 048] - 2025-12-30

### Frontend Migration Phase 4
- Continued frontend migration work
- Backend architecture updates

## [Session 043-046] - 2025-12-27

### Backend Architecture Rework
- Sessions 043-045: Architecture rework phases 1-8
- Session 046: Frontend migration phase 1
- Integrated WhatsApp notifications into FES flow

## [Session 040-042] - 2025-12-25

### Upsell Integrations & Production Prep
- Implemented upsell integrations (Schufa, affiliates, email follow-ups)
- SQL fixes and SuperForms bug fix for production
- WhatsApp FES integration

## Earlier Sessions

See docs/sessions/ for detailed session logs.
