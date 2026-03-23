"""Audit logging service for FES compliance."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.audit_log import SignatureAuditLogRow
from src.models.signature_request import SignatureAuditLog


class AuditService:
    """Service for immutable audit trail logging."""

    VALID_EVENT_TYPES = [
        "request_created",
        "email_sent",
        "link_clicked",
        "document_viewed",
        "consent_given",
        "signed",
        "completed",
        "expired",
        "error",
        "pdf_generated",
        "webhook_sent",
        "webhook_failed",
    ]

    def __init__(self, session: AsyncSession):
        """Initialize audit service with database session."""
        self.session = session

    async def log_event(
        self,
        request_id: UUID,
        event_type: str,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> SignatureAuditLog:
        """Log an audit event (append-only)."""
        if event_type not in self.VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type. Must be one of: {', '.join(self.VALID_EVENT_TYPES)}"
            )

        try:
            row = SignatureAuditLogRow(
                request_id=str(request_id),
                event_type=event_type,
                actor_email=actor_email,
                actor_role=actor_role,
                ip_address=ip_address,
                user_agent=user_agent,
                event_metadata=metadata,
            )
            self.session.add(row)
            await self.session.flush()

            logger.info(
                "Audit event logged",
                request_id=str(request_id),
                event_type=event_type,
                log_id=row.id,
            )
            return self._row_to_model(row)

        except Exception as e:
            logger.error(
                "Failed to log audit event",
                request_id=str(request_id),
                event_type=event_type,
                error=str(e),
            )
            raise

    async def get_audit_trail(self, request_id: UUID) -> list[SignatureAuditLog]:
        """Get complete audit trail in chronological order."""
        stmt = (
            select(SignatureAuditLogRow)
            .where(SignatureAuditLogRow.request_id == str(request_id))
            .order_by(SignatureAuditLogRow.created_at.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return [self._row_to_model(row) for row in rows]

    async def get_events_for_request(self, request_id: UUID) -> list[dict]:
        """Get audit events as dicts for PDF generation."""
        stmt = (
            select(SignatureAuditLogRow)
            .where(SignatureAuditLogRow.request_id == str(request_id))
            .order_by(SignatureAuditLogRow.created_at.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "id": row.id,
                "request_id": row.request_id,
                "event_type": row.event_type,
                "actor_email": row.actor_email,
                "actor_role": row.actor_role,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "metadata": row.event_metadata,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    async def get_events_since(self, request_id: UUID, since: datetime) -> list[dict]:
        """Get audit events created after given timestamp."""
        stmt = (
            select(SignatureAuditLogRow)
            .where(SignatureAuditLogRow.request_id == str(request_id))
            .where(SignatureAuditLogRow.created_at > since)
            .order_by(SignatureAuditLogRow.created_at.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "id": row.id,
                "request_id": row.request_id,
                "event_type": row.event_type,
                "actor_email": row.actor_email,
                "actor_role": row.actor_role,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "metadata": row.event_metadata,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    # Convenience helper methods

    async def log_request_created(
        self, request_id: UUID, requester_email: str, signer_count: int,
        ip_address: Optional[str] = None,
    ) -> SignatureAuditLog:
        return await self.log_event(
            request_id=request_id, event_type="request_created",
            actor_email=requester_email, actor_role="system", ip_address=ip_address,
            metadata={"signer_count": signer_count, "action": "Signature request created"},
        )

    async def log_email_sent(
        self, request_id: UUID, signer_email: str, email_id: Optional[str] = None,
    ) -> SignatureAuditLog:
        return await self.log_event(
            request_id=request_id, event_type="email_sent",
            actor_email=signer_email, actor_role="system",
            metadata={"email_id": email_id, "action": "Signature request email sent"},
        )

    async def log_link_clicked(
        self, request_id: UUID, signer_email: str, ip_address: str, user_agent: str,
    ) -> SignatureAuditLog:
        return await self.log_event(
            request_id=request_id, event_type="link_clicked",
            actor_email=signer_email, actor_role="signer",
            ip_address=ip_address, user_agent=user_agent,
            metadata={"action": "Signing link clicked"},
        )

    async def log_document_viewed(
        self, request_id: UUID, signer_email: str, ip_address: str, user_agent: str,
    ) -> SignatureAuditLog:
        return await self.log_event(
            request_id=request_id, event_type="document_viewed",
            actor_email=signer_email, actor_role="signer",
            ip_address=ip_address, user_agent=user_agent,
            metadata={"action": "Document viewed"},
        )

    async def log_consent_given(
        self, request_id: UUID, signer_email: str, consents: dict, ip_address: str,
    ) -> SignatureAuditLog:
        return await self.log_event(
            request_id=request_id, event_type="consent_given",
            actor_email=signer_email, actor_role="signer", ip_address=ip_address,
            metadata={"action": "GDPR consent given", "consents": consents},
        )

    async def log_signed(
        self, request_id: UUID, signer_email: str, signer_name: str,
        ip_address: str, user_agent: str,
    ) -> SignatureAuditLog:
        return await self.log_event(
            request_id=request_id, event_type="signed",
            actor_email=signer_email, actor_role="signer",
            ip_address=ip_address, user_agent=user_agent,
            metadata={"action": "Signature completed", "signer_name": signer_name},
        )

    async def log_all_completed(self, request_id: UUID, total_signers: int) -> SignatureAuditLog:
        return await self.log_event(
            request_id=request_id, event_type="completed", actor_role="system",
            metadata={"action": "All signatures completed", "total_signers": total_signers},
        )

    async def log_error(
        self, request_id: UUID, error_message: str, error_context: Optional[dict] = None,
    ) -> SignatureAuditLog:
        return await self.log_event(
            request_id=request_id, event_type="error", actor_role="system",
            metadata={"action": "Error occurred", "error_message": error_message,
                       "error_context": error_context},
        )

    def _row_to_model(self, row: SignatureAuditLogRow) -> SignatureAuditLog:
        """Convert SQLAlchemy row to domain model."""
        return SignatureAuditLog(
            id=UUID(row.id),
            request_id=UUID(row.request_id),
            event_type=row.event_type,
            actor_email=row.actor_email,
            actor_role=row.actor_role,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            metadata=row.event_metadata,
            created_at=row.created_at,
        )
