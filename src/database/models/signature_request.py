"""SQLAlchemy models for signature_requests and signature_signers tables."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class SignatureRequestRow(Base):
    """Maps to signature_requests table."""

    __tablename__ = "signature_requests"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    contract_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    requester_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    requester_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Document fields
    document_type: Mapped[str] = mapped_column(String(10), nullable=False, default="pdf")
    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    document_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pdf_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    document_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional
    callback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_email_template_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)

    # Relationships
    signers: Mapped[list["SignatureSignerRow"]] = relationship(
        "SignatureSignerRow", back_populates="request", lazy="selectin"
    )


class SignatureSignerRow(Base):
    """Maps to signature_signers table."""

    __tablename__ = "signature_signers"
    __table_args__ = (
        Index("ix_signers_request_id", "request_id"),
        Index("ix_signers_verification_token", "verification_token", unique=True),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("signature_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    signing_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    verification_method: Mapped[str] = mapped_column(
        String(50), nullable=False, default="email_link"
    )
    verification_token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Signing data
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    geolocation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    signature_image_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    consents: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationship
    request: Mapped["SignatureRequestRow"] = relationship(
        "SignatureRequestRow", back_populates="signers"
    )
