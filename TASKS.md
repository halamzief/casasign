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

### Next Steps

- [ ] E2E Testing: Full signing flow with new Jinja2 templates
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
