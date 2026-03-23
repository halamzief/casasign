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
    document_type: str = "pdf"  # 'pdf', 'json', or 'html'

    # Contract content
    contract_html: str  # Rendered HTML content
    contract_data: Optional[dict] = (
        None  # Raw JSON data (JSON mode only, for client-side re-rendering)
    )
    document_description: str = ""  # Document title/description for display
    sender_name: str = ""  # Name of the person who sent the request

    # Metadata
    is_already_signed: bool
    expires_at: str
    created_at: str


class ConsentSubmission(BaseModel):
    """Consent submission from modal."""

    # Required consents
    identity_confirmed: bool
    contract_reviewed: bool

    # Service-specific additional consents (flexible dict)
    additional_consents: Optional[dict] = None


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
