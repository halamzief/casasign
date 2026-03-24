-- Add attachments JSONB column to signature_requests
-- Stores attachment metadata: [{filename, storage_path, size_bytes}]

ALTER TABLE signature_requests
ADD COLUMN IF NOT EXISTS attachments JSONB DEFAULT NULL;

COMMENT ON COLUMN signature_requests.attachments IS 'Decoded PDF attachment metadata (filename, storage_path, size_bytes)';
