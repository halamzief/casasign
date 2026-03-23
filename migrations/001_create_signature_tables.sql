-- SignCasa Signatures - Database Migration 001
-- FES Signature Service Tables
-- Created: 2025-11-23

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TABLE 1: signature_requests
-- Core signature request tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS signature_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Document reference
  contract_id UUID NOT NULL,              -- Link to main app contract_drafts table
  document_hash VARCHAR(64) NOT NULL,     -- SHA-256 of original PDF
  document_url TEXT NOT NULL,             -- Path to PDF file

  -- Request metadata
  requester_user_id UUID NOT NULL,        -- Who initiated request
  requester_email VARCHAR(255) NOT NULL,
  tenant_id UUID NOT NULL,                -- Multi-tenant isolation

  -- Status tracking
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, in_progress, completed, expired, rejected
  expires_at TIMESTAMP NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
  created_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP NULL,

  -- Callback for main app
  callback_url TEXT NULL,                 -- Webhook URL on completion

  -- Premium features
  custom_email_template_id UUID NULL,     -- NULL = use default with ads

  CONSTRAINT status_check CHECK (status IN ('pending', 'in_progress', 'completed', 'expired', 'rejected'))
);

-- ============================================================================
-- TABLE 2: signature_signers
-- Individual signers for each request
-- ============================================================================
CREATE TABLE IF NOT EXISTS signature_signers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID REFERENCES signature_requests(id) ON DELETE CASCADE,

  -- Signer details
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL,
  phone VARCHAR(20) NULL,                 -- Optional for WhatsApp verification
  role VARCHAR(50) NOT NULL,              -- landlord, tenant_1, tenant_2, witness

  -- Signing workflow
  signing_order INT NOT NULL,             -- 1, 2, 3... for sequential signing
  verification_method VARCHAR(20) NOT NULL DEFAULT 'email_link',
    -- email_link, whatsapp_link (premium)
  verification_token VARCHAR(64) UNIQUE NOT NULL,

  -- Signing metadata
  signed_at TIMESTAMP NULL,
  ip_address INET NULL,
  user_agent TEXT NULL,
  geolocation JSONB NULL,                 -- {city, country, lat, lng}

  -- Signature data
  signature_image_base64 TEXT NULL,       -- Canvas drawing or typed name

  CONSTRAINT verification_check CHECK (verification_method IN ('email_link', 'whatsapp_link'))
);

-- ============================================================================
-- TABLE 3: signature_consents
-- GDPR consent tracking for TENANTS (insurance + utilities opt-ins)
-- ============================================================================
CREATE TABLE IF NOT EXISTS signature_consents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signer_id UUID REFERENCES signature_signers(id) ON DELETE CASCADE,

  -- Required consents (must be true to proceed)
  identity_confirmed BOOLEAN NOT NULL,
  contract_reviewed BOOLEAN NOT NULL,

  -- Optional consents - Insurance (default false)
  deposit_insurance_consent BOOLEAN DEFAULT FALSE,     -- Kautionsversicherung
  tenant_liability_consent BOOLEAN DEFAULT FALSE,      -- Haftpflichtversicherung
  contents_insurance_consent BOOLEAN DEFAULT FALSE,    -- Hausratversicherung

  -- Optional consents - Utilities services (default false)
  energy_signup_consent BOOLEAN DEFAULT FALSE,         -- Strom & Gas
  internet_signup_consent BOOLEAN DEFAULT FALSE,       -- Internet & Telefon
  utilities_reminder_consent BOOLEAN DEFAULT FALSE,    -- Zählerstand reminders
  moving_services_consent BOOLEAN DEFAULT FALSE,       -- Umzugsservice

  -- GDPR audit trail
  consented_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ip_address INET NOT NULL,
  user_agent TEXT,

  -- Withdrawal tracking
  withdrawn_at TIMESTAMP NULL,
  withdrawal_reason TEXT NULL,

  CONSTRAINT required_consents CHECK (identity_confirmed = true AND contract_reviewed = true)
);

-- ============================================================================
-- TABLE 4: landlord_affiliate_consents
-- Landlord affiliate consents (insurance + property mgmt tools)
-- ============================================================================
CREATE TABLE IF NOT EXISTS landlord_affiliate_consents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,                         -- Landlord user ID
  contract_id UUID NULL,                         -- NULL if at registration

  -- Insurance opt-ins
  building_insurance_consent BOOLEAN DEFAULT FALSE,      -- Gebäudeversicherung
  landlord_liability_consent BOOLEAN DEFAULT FALSE,      -- Eigentümerhaftpflicht
  rent_default_insurance_consent BOOLEAN DEFAULT FALSE,  -- Mietausfallversicherung
  legal_protection_consent BOOLEAN DEFAULT FALSE,        -- Rechtsschutz

  -- Property management tools
  property_mgmt_tools_consent BOOLEAN DEFAULT FALSE,

  -- Touchpoint tracking
  consent_source VARCHAR(50) NOT NULL,
    -- registration, contract_wizard, post_signature

  -- GDPR audit trail
  consented_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ip_address INET NOT NULL,
  user_agent TEXT,

  -- Withdrawal tracking
  withdrawn_at TIMESTAMP NULL,
  withdrawal_reason TEXT NULL,

  CONSTRAINT consent_source_check CHECK (consent_source IN (
    'registration', 'contract_wizard', 'post_signature'
  ))
);

-- ============================================================================
-- TABLE 5: signature_audit_log
-- Immutable audit trail (append-only)
-- ============================================================================
CREATE TABLE IF NOT EXISTS signature_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID REFERENCES signature_requests(id) ON DELETE CASCADE,

  -- Event details
  event_type VARCHAR(50) NOT NULL,
    -- request_created, email_sent, link_clicked, document_viewed,
    -- consent_given, signed, completed, expired, error
  actor_email VARCHAR(255),
  actor_role VARCHAR(50),                 -- system, signer, admin

  -- Context
  ip_address INET,
  user_agent TEXT,
  metadata JSONB,                         -- Additional event-specific data

  -- Immutable timestamp
  created_at TIMESTAMP DEFAULT NOW(),

  CONSTRAINT event_type_check CHECK (event_type IN (
    'request_created', 'email_sent', 'link_clicked', 'document_viewed',
    'consent_given', 'signed', 'completed', 'expired', 'error'
  ))
);

-- ============================================================================
-- TABLE 6: email_templates
-- Email templates (editable in admin UI)
-- ============================================================================
CREATE TABLE IF NOT EXISTS email_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NULL,                    -- NULL = system default

  -- Template identification
  template_key VARCHAR(50) NOT NULL,
    -- signature_request, signature_completed, reminder, signature_rejected
  name VARCHAR(100) NOT NULL,             -- Display name in admin UI
  description TEXT,

  -- Template content (Jinja2)
  subject_template TEXT NOT NULL,
  body_html TEXT NOT NULL,
  body_text TEXT NOT NULL,                -- Plain text fallback

  -- Metadata
  language VARCHAR(5) DEFAULT 'de',
  is_default BOOLEAN DEFAULT FALSE,       -- System default with ads
  is_active BOOLEAN DEFAULT TRUE,

  -- Versioning
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  updated_by UUID NULL,                   -- User who last edited

  UNIQUE(tenant_id, template_key, language)
);

-- ============================================================================
-- INDEXES for Performance
-- ============================================================================

-- signature_requests indexes
CREATE INDEX IF NOT EXISTS idx_signature_requests_status
  ON signature_requests(status);
CREATE INDEX IF NOT EXISTS idx_signature_requests_contract
  ON signature_requests(contract_id);
CREATE INDEX IF NOT EXISTS idx_signature_requests_tenant
  ON signature_requests(tenant_id);
CREATE INDEX IF NOT EXISTS idx_signature_requests_expires
  ON signature_requests(expires_at);

-- signature_signers indexes
CREATE INDEX IF NOT EXISTS idx_signature_signers_request
  ON signature_signers(request_id);
CREATE INDEX IF NOT EXISTS idx_signature_signers_token
  ON signature_signers(verification_token);
CREATE INDEX IF NOT EXISTS idx_signature_signers_email
  ON signature_signers(email);

-- signature_consents indexes
CREATE INDEX IF NOT EXISTS idx_signature_consents_signer
  ON signature_consents(signer_id);
CREATE INDEX IF NOT EXISTS idx_signature_consents_date
  ON signature_consents(consented_at DESC);

-- landlord_affiliate_consents indexes
CREATE INDEX IF NOT EXISTS idx_landlord_consents_user
  ON landlord_affiliate_consents(user_id);
CREATE INDEX IF NOT EXISTS idx_landlord_consents_contract
  ON landlord_affiliate_consents(contract_id);
CREATE INDEX IF NOT EXISTS idx_landlord_consents_source
  ON landlord_affiliate_consents(consent_source);

-- signature_audit_log indexes
CREATE INDEX IF NOT EXISTS idx_signature_audit_log_request
  ON signature_audit_log(request_id);
CREATE INDEX IF NOT EXISTS idx_signature_audit_log_created
  ON signature_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signature_audit_log_event_type
  ON signature_audit_log(event_type);

-- email_templates indexes
CREATE INDEX IF NOT EXISTS idx_email_templates_key
  ON email_templates(template_key, language);
CREATE INDEX IF NOT EXISTS idx_email_templates_tenant
  ON email_templates(tenant_id);

-- ============================================================================
-- COMMENTS for Documentation
-- ============================================================================

COMMENT ON TABLE signature_requests IS 'Core signature requests with FES compliance tracking';
COMMENT ON TABLE signature_signers IS 'Individual signers with verification tokens and metadata';
COMMENT ON TABLE signature_consents IS 'GDPR consent tracking for tenant insurance + utilities opt-ins';
COMMENT ON TABLE landlord_affiliate_consents IS 'Landlord insurance + property management opt-ins';
COMMENT ON TABLE signature_audit_log IS 'Immutable audit trail for eIDAS FES compliance';
COMMENT ON TABLE email_templates IS 'Customizable Jinja2 email templates with multi-language support';

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE signature_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE signature_signers ENABLE ROW LEVEL SECURITY;
ALTER TABLE signature_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE landlord_affiliate_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE signature_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_templates ENABLE ROW LEVEL SECURITY;

-- Service role bypass (for microservice operations)
CREATE POLICY "Service role has full access to signature_requests"
  ON signature_requests FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role has full access to signature_signers"
  ON signature_signers FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role has full access to signature_consents"
  ON signature_consents FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role has full access to landlord_affiliate_consents"
  ON landlord_affiliate_consents FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role has full access to signature_audit_log"
  ON signature_audit_log FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role has full access to email_templates"
  ON email_templates FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- ============================================================================
-- Migration Complete
-- ============================================================================
