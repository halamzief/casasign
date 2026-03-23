"""Signature request Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# =============================================================================
# Contract Data Schemas (for JSON-to-HTML mode)
# =============================================================================


class ContractMetadataSchema(BaseModel):
    """Metadata about the contract."""

    contract_id: str
    contract_number: Optional[str] = None
    created_at: Optional[str] = None


class VermieterSchema(BaseModel):
    """Landlord (Vermieter) data."""

    name: str = ""
    email: Optional[EmailStr] = None  # Optional - may not be set yet
    phone: Optional[str] = None
    anschrift: Optional[str] = None


class AnschriftSchema(BaseModel):
    """Address schema."""

    strasse: str
    hausnummer: str
    plz: str
    stadt: str


class MieterSchema(BaseModel):
    """Tenant (Mieter) data."""

    vorname: str = ""
    nachname: str = ""
    geburtstag: Optional[str] = None  # YYYY-MM-DD
    email: Optional[EmailStr] = None  # Optional - contract may not have email yet
    telefon: Optional[str] = None
    anschrift: Optional[AnschriftSchema] = None


class StellplatzSchema(BaseModel):
    """Parking space data."""

    typ: str  # aussenstellplatz, tiefgarage, garage, kein_stellplatz
    nummer: Optional[str] = None


class MietobjektSchema(BaseModel):
    """Property (Mietobjekt) data."""

    liegenschaft: Optional[str] = None
    strasse: str = ""
    hausnummer: str = ""
    plz: str = ""
    ort: str = ""
    lage: Optional[str] = None  # Floor/unit
    zimmer_anzahl: Optional[int] = None
    personenanzahl: Optional[int] = None
    stellplatz: Optional[StellplatzSchema] = None
    kellerraum_nummer: Optional[str] = None


class MietzeitSchema(BaseModel):
    """Rental period data."""

    beginn: str = ""  # YYYY-MM-DD - default empty if not set
    ende: Optional[str] = None  # YYYY-MM-DD (null = unlimited)
    mindestmietzeit_monate: Optional[int] = None
    befristet: bool = False
    besichtigungsdatum: Optional[str] = None


class MieteSchema(BaseModel):
    """Rent data."""

    kaltmiete: float
    betriebskosten: float = 0.0
    heizkosten: float = 0.0
    gesamtmiete: float


class KautionSchema(BaseModel):
    """Security deposit data."""

    betrag: float


class BankverbindungSchema(BaseModel):
    """Bank account data."""

    bank_name: str = ""
    iban: str = ""
    bic: Optional[str] = None
    verwendungszweck: Optional[str] = None


class VereinbarungenSchema(BaseModel):
    """Other agreements."""

    besonderheiten: Optional[str] = None
    sonstige: Optional[str] = None


class ContractDataSchema(BaseModel):
    """Complete contract data for JSON-to-HTML rendering.

    This replaces the need for uploading a PDF upfront.
    The contract is rendered as HTML for the signer and
    converted to PDF only after all signatures are collected.
    """

    metadata: ContractMetadataSchema
    vermieter: VermieterSchema
    mieter1: MieterSchema
    mieter2: Optional[MieterSchema] = None
    mietobjekt: MietobjektSchema
    mietzeit: MietzeitSchema
    miete: MieteSchema
    kaution: KautionSchema
    bankverbindung: BankverbindungSchema
    vereinbarungen: Optional[VereinbarungenSchema] = None


# =============================================================================
# Signer Schemas
# =============================================================================


class SignerCreate(BaseModel):
    """Schema for creating a signer."""

    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    role: str = Field(..., max_length=50)  # landlord, tenant_1, tenant_2, witness
    signing_order: int = Field(..., ge=1, le=10)
    verification_method: str = Field(default="email_link")

    @field_validator("verification_method")
    @classmethod
    def validate_verification_method(cls, v: str) -> str:
        """Validate verification method."""
        if v not in ["email_link", "whatsapp_link"]:
            raise ValueError("verification_method must be 'email_link' or 'whatsapp_link'")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role."""
        allowed_roles = ["landlord", "tenant_1", "tenant_2", "tenant_3", "witness", "guarantor"]
        if v not in allowed_roles:
            raise ValueError(f"role must be one of: {', '.join(allowed_roles)}")
        return v


class SignatureRequestCreate(BaseModel):
    """Schema for creating a signature request.

    Supports three document modes:
    1. PDF mode (legacy): Provide document_pdf_base64
    2. JSON mode: Provide contract_data for server-side HTML rendering
    3. HTML mode: Provide document_html with pre-rendered HTML from caller
    """

    contract_id: UUID
    # PDF mode (legacy) - base64-encoded PDF document
    document_pdf_base64: Optional[str] = Field(
        None, description="Base64-encoded PDF document (PDF mode)"
    )
    # JSON mode - contract data for HTML rendering
    contract_data: Optional[ContractDataSchema] = Field(
        None, description="Contract data for HTML rendering (JSON mode)"
    )
    # HTML mode - pre-rendered HTML from caller
    document_html: Optional[str] = Field(
        None, description="Pre-rendered HTML document content (HTML mode)"
    )
    # Document metadata
    document_title: Optional[str] = Field(None, description="Document title for display")
    document_name: Optional[str] = Field(None, description="Document filename")
    sender_name: Optional[str] = Field(None, description="Name of the sender/requester")
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
        """Ensure exactly one document source is provided."""
        has_pdf = self.document_pdf_base64 is not None
        has_json = self.contract_data is not None
        has_html = self.document_html is not None
        sources = sum([has_pdf, has_json, has_html])

        if sources > 1:
            raise ValueError("Provide only one of: document_pdf_base64, contract_data, document_html")
        if sources == 0:
            raise ValueError("Must provide one of: document_pdf_base64, contract_data, or document_html")

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
    document_hash: Optional[str] = None  # Nullable for JSON mode
    document_type: str = "pdf"  # 'pdf' or 'json'
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
