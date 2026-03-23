"""SQLAlchemy model for signature_audit_log table."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class SignatureAuditLogRow(Base):
    """Maps to signature_audit_log table (append-only)."""

    __tablename__ = "signature_audit_log"
    __table_args__ = (Index("ix_audit_request_created", "request_id", "created_at"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("signature_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
