"""Signature request repository for PostgreSQL database operations."""

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import settings
from src.database.models.signature_request import SignatureRequestRow, SignatureSignerRow
from src.models.signature_request import SignatureRequest, SignatureSigner
from src.schemas.signature import SignerCreate
from src.utils.hash_utils import calculate_sha256_from_base64
from src.utils.token_generator import generate_verification_token


class SignatureRepository:
    """Repository for signature request database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def create_request(
        self,
        contract_id: UUID,
        requester_user_id: UUID,
        requester_email: str,
        tenant_id: UUID,
        signers: list[SignerCreate],
        document_pdf_base64: Optional[str] = None,
        contract_data: Optional[dict] = None,
        document_html: Optional[str] = None,
        document_title: Optional[str] = None,
        document_name: Optional[str] = None,
        sender_name: Optional[str] = None,
        callback_url: Optional[str] = None,
        custom_email_template_id: Optional[UUID] = None,
        expires_in_days: int = 7,
        attachments: Optional[list[dict]] = None,
        sections: Optional[list[dict]] = None,
    ) -> tuple[SignatureRequest, list[SignatureSigner]]:
        """Create signature request with signers."""
        if document_html is not None:
            document_type = "html"
        elif contract_data is not None:
            document_type = "json"
        else:
            document_type = "pdf"

        logger.info(
            "Creating signature request",
            contract_id=str(contract_id),
            document_type=document_type,
            signer_count=len(signers),
        )

        try:
            request_id = uuid4()

            if document_type in ("json", "html"):
                document_hash = None
                document_url = None
            else:
                if not document_pdf_base64:
                    raise ValueError("document_pdf_base64 required for PDF mode")
                document_hash = calculate_sha256_from_base64(document_pdf_base64)
                document_url = await self._save_pdf(request_id, document_pdf_base64)

            # Process attachments: decode base64 and save to disk
            attachment_metadata = None
            if attachments:
                attachment_metadata = []
                for att in attachments:
                    att_path = self._save_attachment(
                        request_id=request_id,
                        filename=att["filename"],
                        content_base64=att["content_base64"],
                    )
                    attachment_metadata.append(
                        {
                            "filename": att["filename"],
                            "storage_path": str(att_path),
                            "size_bytes": att["size_bytes"],
                        }
                    )

            # Merge sections into contract_data for template rendering
            if sections and contract_data:
                contract_data["sections"] = sections

            # Create request row
            request_row = SignatureRequestRow(
                id=str(request_id),
                contract_id=str(contract_id),
                document_hash=document_hash,
                document_url=document_url,
                contract_data=contract_data,
                document_html=document_html,
                attachments=attachment_metadata,
                document_type=document_type,
                document_title=document_title,
                document_name=document_name,
                sender_name=sender_name,
                requester_user_id=str(requester_user_id),
                requester_email=requester_email,
                tenant_id=str(tenant_id),
                status="pending",
                expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
                callback_url=callback_url,
                custom_email_template_id=(
                    str(custom_email_template_id) if custom_email_template_id else None
                ),
            )
            self.session.add(request_row)
            await self.session.flush()

            # Create signer rows
            signer_models = []
            for signer in signers:
                token = generate_verification_token()
                signer_row = SignatureSignerRow(
                    id=str(uuid4()),
                    request_id=str(request_id),
                    name=signer.name,
                    email=signer.email,
                    phone=signer.phone,
                    role=signer.role,
                    signing_order=signer.signing_order,
                    verification_method=signer.verification_method,
                    verification_token=token,
                )
                self.session.add(signer_row)
                signer_models.append(self._signer_row_to_model(signer_row))

            await self.session.flush()

            request_model = self._request_row_to_model(request_row)
            logger.success(
                "Signature request created",
                request_id=str(request_id),
                document_type=document_type,
                signer_count=len(signer_models),
            )

            return request_model, signer_models

        except Exception as e:
            logger.error(f"Failed to create signature request: {e!s}")
            raise

    async def get_request_by_id(self, request_id: UUID) -> Optional[SignatureRequest]:
        """Get signature request by ID with signers."""
        stmt = (
            select(SignatureRequestRow)
            .options(selectinload(SignatureRequestRow.signers))
            .where(SignatureRequestRow.id == str(request_id))
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            return self._request_row_to_model(row)
        return None

    async def get_signers_by_request(self, request_id: UUID) -> list[SignatureSigner]:
        """Get all signers for a request ordered by signing_order."""
        stmt = (
            select(SignatureSignerRow)
            .where(SignatureSignerRow.request_id == str(request_id))
            .order_by(SignatureSignerRow.signing_order)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return [self._signer_row_to_model(row) for row in rows]

    async def get_signer_by_token(self, token: str) -> Optional[SignatureSigner]:
        """Get signer by verification token."""
        stmt = select(SignatureSignerRow).where(SignatureSignerRow.verification_token == token)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            return self._signer_row_to_model(row)
        return None

    async def update_request_status(
        self, request_id: UUID, status: str, completed_at: Optional[datetime] = None
    ) -> None:
        """Update signature request status."""
        values: dict = {"status": status}
        if completed_at:
            values["completed_at"] = completed_at

        stmt = (
            update(SignatureRequestRow)
            .where(SignatureRequestRow.id == str(request_id))
            .values(**values)
        )
        await self.session.execute(stmt)
        logger.info("Request status updated", request_id=str(request_id), status=status)

    async def update_request_pdf_generated(
        self,
        request_id: UUID,
        pdf_generated_at: datetime,
        document_hash: str | None = None,
    ) -> None:
        """Update pdf_generated_at timestamp and optional document hash (JSON/HTML mode)."""
        values: dict = {"pdf_generated_at": pdf_generated_at}
        if document_hash:
            values["document_hash"] = document_hash
        stmt = (
            update(SignatureRequestRow)
            .where(SignatureRequestRow.id == str(request_id))
            .values(**values)
        )
        await self.session.execute(stmt)
        logger.info(
            "Request pdf_generated_at updated",
            request_id=str(request_id),
            has_hash=bool(document_hash),
        )

    async def mark_signer_signed(
        self,
        signer_id: UUID,
        signature_image_base64: str,
        ip_address: str,
        user_agent: str,
        geolocation: Optional[dict] = None,
        consents: Optional[dict] = None,
    ) -> None:
        """Mark signer as signed."""
        stmt = (
            update(SignatureSignerRow)
            .where(SignatureSignerRow.id == str(signer_id))
            .values(
                signed_at=datetime.now(timezone.utc),
                signature_image_base64=signature_image_base64,
                ip_address=ip_address,
                user_agent=user_agent,
                geolocation=geolocation,
                consents=consents,
            )
        )
        await self.session.execute(stmt)
        logger.info("Signer marked as signed", signer_id=str(signer_id))

    async def _save_pdf(self, request_id: UUID, pdf_base64: str) -> str:
        """Save PDF to local filesystem."""
        storage_path = Path(settings.signatures_storage_path)
        storage_path.mkdir(parents=True, exist_ok=True)

        filename = f"{request_id}.pdf"
        file_path = storage_path / filename

        pdf_content = base64.b64decode(pdf_base64)
        with open(file_path, "wb") as f:
            f.write(pdf_content)

        logger.debug("PDF saved to filesystem", path=str(file_path))
        return f"{settings.signatures_storage_path}/{filename}"

    def _save_attachment(self, request_id: UUID, filename: str, content_base64: str) -> Path:
        """Decode base64 PDF and save to disk."""
        att_dir = Path(settings.signatures_storage_path) / "attachments" / str(request_id)
        att_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name  # Prevent directory traversal
        file_path = att_dir / safe_name
        file_data = base64.b64decode(content_base64)
        file_path.write_bytes(file_data)
        logger.info(f"Saved attachment: {file_path} ({len(file_data)} bytes)")
        return file_path

    def _request_row_to_model(self, row: SignatureRequestRow) -> SignatureRequest:
        """Convert SQLAlchemy row to domain model."""
        return SignatureRequest(
            id=UUID(row.id),
            contract_id=UUID(row.contract_id),
            requester_user_id=UUID(row.requester_user_id),
            requester_email=row.requester_email,
            tenant_id=UUID(row.tenant_id),
            document_hash=row.document_hash,
            document_url=row.document_url,
            contract_data=row.contract_data,
            document_type=row.document_type,
            pdf_generated_at=row.pdf_generated_at,
            attachments=getattr(row, "attachments", None),
            document_html=getattr(row, "document_html", None),
            document_title=getattr(row, "document_title", None),
            document_name=getattr(row, "document_name", None),
            sender_name=getattr(row, "sender_name", None),
            status=row.status,
            expires_at=row.expires_at,
            created_at=row.created_at,
            completed_at=row.completed_at,
            callback_url=row.callback_url,
            custom_email_template_id=(
                UUID(row.custom_email_template_id) if row.custom_email_template_id else None
            ),
        )

    def _signer_row_to_model(self, row: SignatureSignerRow) -> SignatureSigner:
        """Convert SQLAlchemy row to domain model."""
        return SignatureSigner(
            id=UUID(row.id),
            request_id=UUID(row.request_id),
            name=row.name,
            email=row.email,
            phone=row.phone,
            role=row.role,
            signing_order=row.signing_order,
            verification_method=row.verification_method,
            verification_token=row.verification_token,
            signed_at=row.signed_at,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            geolocation=row.geolocation,
            signature_image_base64=row.signature_image_base64,
            consents=getattr(row, "consents", None),
        )
