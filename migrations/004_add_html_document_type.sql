-- CasaSign - Database Migration 004
-- Add 'html' document type for pre-rendered HTML mode
-- Created: 2026-03-23
--
-- Purpose: Support HTML mode where the caller sends pre-rendered HTML
-- instead of contract_data (JSON mode) or PDF bytes (PDF mode).

-- Update document_type check constraint to include 'html'
ALTER TABLE signature_requests
  DROP CONSTRAINT IF EXISTS document_type_check;

ALTER TABLE signature_requests
  ADD CONSTRAINT document_type_check
  CHECK (document_type IN ('pdf', 'json', 'html'));

-- Add document_html column for storing pre-rendered HTML
ALTER TABLE signature_requests
  ADD COLUMN IF NOT EXISTS document_html TEXT NULL;

COMMENT ON COLUMN signature_requests.document_html IS
  'Pre-rendered HTML document content (HTML mode). Caller provides ready-to-display HTML.';

COMMENT ON COLUMN signature_requests.document_type IS
  'Request mode: pdf=PDF-upfront, json=JSON-to-HTML rendering, html=pre-rendered HTML';
