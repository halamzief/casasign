# Tasks

## Current Sprint: Frontend Migration

### Completed

- [x] Phase 1: Auth Pages (Session 046)
- [x] Phase 2: Contract Wizard (Session 046)
- [x] Phase 3: Dashboard Pages (Session 047)
- [x] Phase 4: Admin Pages (Session 048)
- [x] Phase 5: Profile/Billing Pages (Session 048)
- [x] Phase 6: Shared Components (Session 048)
- [x] **Phase 7: FES Jinja2 Migration** (Session 049)
  - Base template with Tailwind/htmx/Alpine.js CDN
  - SignaturePad.svelte -> vanilla JS class (signature_pad library)
  - ConsentModal.svelte -> Alpine.js x-data component
  - ContractPreview.svelte -> Jinja2 macros
  - Signing page orchestration
  - Success page with affiliate links
- [x] **Phase 8: SvelteKit Deletion** (Session 049)
  - Removed frontend/ SvelteKit directory
  - Removed frontend service from docker-compose.yml

### Attachment + Section Support (Session 083) -- DONE

- [x] AttachmentSchema + SectionSchema with nh3 HTML sanitization
- [x] `attachments` JSONB column on signature_requests + migration 005
- [x] Store attachments to disk, merge sections into contract_data
- [x] Include PDF attachments in signing invitation emails (Resend SDK)
- [x] Section-driven rendering with override support
- [x] Section override support in PDF template
- [x] Merge attachment PDFs into final signed document (pypdf)
- [x] 14 schema validation tests

### Success Page + Typed Signatures + Consent Storage (Session 086) -- DONE

- [x] Success page redesign (moving checklist, real info cards, umlauts fixed)
- [x] Dual-mode signature pad (draw + type with 3 handwriting fonts)
- [x] Consent capture: optional service consents (energy, internet)
- [x] Consent storage: `consents` JSONB column on signature_signers (migration 006)
- [x] Full backend chain: model, repository, service, API
- [x] Success page data extraction bug fix (.get() on model object)

### Section Extraction (Session 084) -- DONE

- [x] Full section default extraction (16 partials, dynamic includes, section-driven rendering)
- [x] Fixed pre-existing test failures (Pydantic v2 regex)
- [x] 48/48 tests passing

### Next Steps

- [ ] E2E Testing: Full signing flow with attachments and section overrides
- [ ] Integration Testing: Verify all API endpoints work with templates
- [ ] Production Deployment: Deploy FES with new frontend
- [ ] Performance Testing: Compare SvelteKit vs Jinja2 performance

## Backlog

### High Priority
- [ ] Add PDF preview loading state
- [ ] Implement signature retry on network failure
- [ ] Add mobile-responsive signature pad

### Medium Priority
- [ ] WhatsApp verification flow improvements
- [ ] Email template refresh
- [ ] Audit trail export functionality

### Low Priority
- [ ] Analytics dashboard
- [ ] A/B testing for consent modal
- [ ] Multi-language support (DE/EN)

## Tech Debt

- [ ] Clean up legacy session markdown files in root
- [ ] Consolidate template directories
- [ ] Add mypy strict mode to CI
