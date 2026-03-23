"""Signature request Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# =============================================================================
# Signer Schemas
# =============================================================================


class SignerCreate(BaseModel):
    """Schema for creating a signer."""

    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    role: str = Field(..., max_length=50)  # Any string role (e.g. sender, signer, witness)
    signing_order: int = Field(..., ge=1, le=10)
    verification_method: str = Field(default="email_link")

    @field_validator("verification_method")
    @classmethod
    def validate_verification_method(cls, v: str) -> str:
        """Validate verification method."""
        if v not in ["email_link", "whatsapp_link"]:
            raise ValueError("verification_method must be 'email_link' or 'whatsapp_link'")
        return v


class SignatureRequestCreate(BaseModel):
    """Schema for creating a signature request.

    Supports three document modes:
    1. PDF mode: Provide document_pdf_base64
    2. JSON mode: Provide contract_data (dict)
    3. HTML mode: Provide document_html
    """

    contract_id: UUID
    # PDF mode - base64-encoded PDF document
    document_pdf_base64: Optional[str] = Field(
        None, description="Base64-encoded PDF document (PDF mode)"
    )
    # JSON mode - arbitrary data dict for key-value HTML rendering
    contract_data: Optional[dict] = Field(
        None, description="Arbitrary data dict for HTML rendering (JSON mode)"
    )
    # HTML mode - pre-rendered HTML content
    document_html: Optional[str] = Field(
        None, description="Pre-rendered HTML document content (HTML mode)"
    )
    # Generic document metadata
    document_title: str = Field(default="Dokument", max_length=500)
    document_name: Optional[str] = Field(None, max_length=255)
    sender_name: str = Field(default="", max_length=255)
    email_variables: Optional[dict] = Field(
        None, description="Custom variables for email templates"
    )
    # Requester info - REQUIRED (database has NOT NULL constraints)
    requester_user_id: UUID = Field(..., description="UUID of the user requesting the signature")
    requester_email: EmailStr = Field(..., description="Email of the requester")
    tenant_id: UUID = Field(..., description="Tenant ID for multi-tenant isolation")
    signers: list[SignerCreate] = Field(..., min_length=1, max_length=10)
    callback_url: Optional[str] = None
    custom_email_template_id: Optional[UUID] = None
    expires_in_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode="after")
    def validate_document_source(self) -> "SignatureRequestCreate":
        """Ensure at least one document source is provided."""
        has_pdf = self.document_pdf_base64 is not None
        has_json = self.contract_data is not None
        has_html = self.document_html is not None

        sources = sum([has_pdf, has_json, has_html])
        if sources > 1:
            raise ValueError(
                "Provide only one of: document_pdf_base64, contract_data, or document_html"
            )
        if sources == 0:
            raise ValueError(
                "Must provide one of: document_pdf_base64, contract_data, or document_html"
            )

        return self

    @property
    def document_type(self) -> str:
        """Return the document type based on provided data."""
        if self.document_html is not None:
            return "html"
        if self.contract_data is not None:
            return "json"
        return "pdf"


class SignerResponse(BaseModel):
    """Schema for signer response."""

    id: UUID
    name: str
    email: EmailStr
    phone: Optional[str]
    role: str
    signing_order: int
    verification_method: str
    signed_at: Optional[datetime]
    signing_link: Optional[str] = None  # Generated dynamically

    class Config:
        """Pydantic config."""

        from_attributes = True


class SignatureRequestResponse(BaseModel):
    """Schema for signature request response."""

    id: UUID
    contract_id: UUID
    document_hash: Optional[str] = None  # Nullable for JSON/HTML mode
    document_type: str = "pdf"  # 'pdf', 'json', or 'html'
    status: str
    signers: list[SignerResponse]
    expires_at: datetime
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class SignatureRequestStatusResponse(BaseModel):
    """Schema for signature request status."""

    id: UUID
    status: str  # pending, in_progress, completed, expired, rejected
    total_signers: int
    signed_count: int
    pending_signers: list[str]  # List of pending signer names
    expires_at: datetime
    created_at: datetime
    completed_at: Optional[datetime]


class SignatureCompleteRequest(BaseModel):
    """Schema for completing signature."""

    token: str = Field(..., min_length=64, max_length=64)
    signature_image_base64: str = Field(..., description="Canvas signature as base64 PNG")
    ip_address: str
    user_agent: str
    geolocation: Optional[dict] = None


class SignatureCompleteResponse(BaseModel):
    """Schema for signature completion response."""

    success: bool
    message: str
    request_id: UUID
    signer_id: UUID
    signed_at: datetime
    next_signer: Optional[str] = None  # Name of next signer
    all_completed: bool


class AuditLogEntry(BaseModel):
    """Schema for audit log entry."""

    id: UUID
    request_id: UUID
    event_type: str
    actor_email: Optional[str]
    actor_role: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Optional[dict]
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True
