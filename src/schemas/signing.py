"""Schemas for signing flow endpoints."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class TokenValidationResponse(BaseModel):
    """Response for token validation."""

    # Signer information
    signer_id: UUID
    signer_name: str
    signer_email: EmailStr
    signer_role: str
    signing_order: int

    # Request information
    request_id: UUID
    contract_id: UUID
    status: str  # pending, in_progress, completed, expired

    # Document mode
    document_type: str = "pdf"  # 'pdf' or 'json'

    # Contract content
    contract_html: str  # Rendered HTML content
    contract_data: Optional[dict] = (
        None  # Raw JSON data (JSON mode only, for client-side re-rendering)
    )
    property_address: str  # For display
    landlord_name: str

    # Metadata
    is_already_signed: bool
    expires_at: str
    created_at: str


class ConsentSubmission(BaseModel):
    """Consent submission from modal."""

    # Required consents
    identity_confirmed: bool
    contract_reviewed: bool

    # Optional - Insurance
    deposit_insurance_consent: bool = False
    tenant_liability_consent: bool = False
    contents_insurance_consent: bool = False

    # Optional - Utilities
    energy_signup_consent: bool = False
    internet_signup_consent: bool = False
    utilities_reminder_consent: bool = False
    moving_services_consent: bool = False


class SignatureSubmission(BaseModel):
    """Signature submission."""

    signature_image_base64: str  # Canvas signature as PNG
    consents: ConsentSubmission


class SigningCompleteResponse(BaseModel):
    """Response after signing."""

    success: bool
    message: str
    request_id: UUID
    signer_id: UUID
    signed_at: str
    next_signer_name: Optional[str] = None
    all_completed: bool
