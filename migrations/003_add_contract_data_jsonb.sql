-- SignCasa Signatures - Database Migration 003
-- Add contract_data JSONB for JSON-to-HTML architecture
-- Created: 2025-12-16
--
-- Purpose: Enable JSON-based contract rendering instead of PDF-upfront
-- Benefits: Faster mobile load, less storage, better UX

-- ============================================================================
-- STEP 1: Add new columns to signature_requests
-- ============================================================================

-- contract_data: Store full contract JSON for HTML rendering
ALTER TABLE signature_requests
  ADD COLUMN IF NOT EXISTS contract_data JSONB NULL;

-- document_type: Track which mode the request uses
-- 'pdf' = legacy PDF-upfront mode (existing behavior)
-- 'json' = new JSON-to-HTML mode
ALTER TABLE signature_requests
  ADD COLUMN IF NOT EXISTS document_type VARCHAR(10) NOT NULL DEFAULT 'pdf';

-- pdf_generated_at: Track when final PDF was generated (JSON mode only)
ALTER TABLE signature_requests
  ADD COLUMN IF NOT EXISTS pdf_generated_at TIMESTAMP NULL;

-- ============================================================================
-- STEP 2: Make document_url and document_hash nullable for JSON mode
-- ============================================================================

-- document_url is only required for PDF mode; JSON mode generates PDF at completion
ALTER TABLE signature_requests
  ALTER COLUMN document_url DROP NOT NULL;

-- document_hash is only available after PDF exists
ALTER TABLE signature_requests
  ALTER COLUMN document_hash DROP NOT NULL;

-- ============================================================================
-- STEP 3: Add constraint for document_type validation
-- ============================================================================

-- Ensure document_type is valid
ALTER TABLE signature_requests
  DROP CONSTRAINT IF EXISTS document_type_check;

ALTER TABLE signature_requests
  ADD CONSTRAINT document_type_check
  CHECK (document_type IN ('pdf', 'json'));

-- ============================================================================
-- STEP 4: Add GIN index for efficient JSONB queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_signature_requests_contract_data_gin
  ON signature_requests USING GIN (contract_data);

-- Index for filtering by document_type
CREATE INDEX IF NOT EXISTS idx_signature_requests_document_type
  ON signature_requests(document_type);

-- ============================================================================
-- STEP 5: Add comments for documentation
-- ============================================================================

COMMENT ON COLUMN signature_requests.contract_data IS
  'JSON contract data for HTML rendering (JSON-to-HTML mode). Contains vermieter, mieter, mietobjekt, etc.';

COMMENT ON COLUMN signature_requests.document_type IS
  'Request mode: pdf=legacy PDF-upfront, json=new JSON-to-HTML rendering';

COMMENT ON COLUMN signature_requests.pdf_generated_at IS
  'Timestamp when final PDF was generated (JSON mode only, after all signatures)';

-- ============================================================================
-- Migration Complete
-- ============================================================================
