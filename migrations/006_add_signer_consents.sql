-- Migration 006: Add consents JSONB column to signature_signers
-- Stores consent choices made during signing (energy, internet, etc.)
-- Used to personalize the post-signature success page.

ALTER TABLE signature_signers
    ADD COLUMN IF NOT EXISTS consents JSONB DEFAULT NULL;

COMMENT ON COLUMN signature_signers.consents IS 'Consent choices from signing page (energy, internet, etc.)';
