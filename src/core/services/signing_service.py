"""Signing flow service - handles token validation and signature completion."""

from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from src.config import settings
from src.core.audit.audit_service import AuditService
from src.core.email.resend_service import ResendEmailService
from src.core.repositories.signature_repository import SignatureRepository
from src.models.signature_request import SignatureSigner
from src.schemas.signing import ConsentSubmission, TokenValidationResponse


class SigningService:
    """Service for signing flow operations."""

    def __init__(
        self,
        signature_repo: SignatureRepository,
        audit_service: AuditService,
        email_service: ResendEmailService,
    ):
        """Initialize service."""
        self.signature_repo = signature_repo
        self.audit_service = audit_service
        self.email_service = email_service

    async def validate_token_and_get_contract(
        self,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenValidationResponse:
        """Validate signing token and return document data.

        Args:
            token: Verification token from email link
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            TokenValidationResponse with document and signer data

        Raises:
            ValueError: If token invalid or expired
        """
        logger.info("Validating token", token=token[:10] + "...")

        # Get signer by token
        signer = await self.signature_repo.get_signer_by_token(token)

        if not signer:
            logger.warning("Invalid token", token=token[:10] + "...")
            raise ValueError("Invalid or expired signing link")

        # Get signature request
        request = await self.signature_repo.get_request_by_id(signer.request_id)

        if not request:
            raise ValueError("Signature request not found")

        # Check if expired (handle timezone-aware comparison)
        if request.expires_at:
            expires_at = request.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                logger.warning("Token expired", request_id=str(request.id))
                raise ValueError("Signing link has expired")

        # Check if already signed
        is_already_signed = signer.signed_at is not None

        # Log link clicked
        await self.audit_service.log_link_clicked(
            request_id=request.id,
            signer_email=signer.email,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown",
        )

        # Generate document HTML based on document type
        contract_html = self._resolve_document_html(request)
        contract_data = request.contract_data if request.is_json_mode else None

        logger.success(
            "Token validated",
            request_id=str(request.id),
            document_type=request.document_type,
            signer_email=signer.email,
            is_already_signed=is_already_signed,
        )

        return TokenValidationResponse(
            signer_id=signer.id,
            signer_name=signer.name,
            signer_email=signer.email,
            signer_role=signer.role,
            signing_order=signer.signing_order,
            request_id=request.id,
            contract_id=request.contract_id,
            status=request.status,
            document_type=request.document_type,
            contract_html=contract_html,
            contract_data=contract_data,
            document_description=request.document_title,
            sender_name=request.sender_name,
            is_already_signed=is_already_signed,
            expires_at=str(request.expires_at),
            created_at=str(request.created_at),
        )

    async def complete_signature(
        self,
        token: str,
        signature_image_base64: str,
        consents: ConsentSubmission,
        ip_address: str,
        user_agent: str,
    ) -> dict:
        """Complete signature and store consents.

        Args:
            token: Verification token
            signature_image_base64: Canvas signature as base64 PNG
            consents: Consents data
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Dict with completion status

        Raises:
            ValueError: If token invalid or already signed
        """
        logger.info("Completing signature", token=token[:10] + "...")

        # Get signer
        signer = await self.signature_repo.get_signer_by_token(token)

        if not signer:
            raise ValueError("Invalid signing link")

        if signer.signed_at:
            raise ValueError("Document already signed")

        # Get request
        request = await self.signature_repo.get_request_by_id(signer.request_id)

        if not request:
            raise ValueError("Signature request not found")

        # Mark signer as signed
        await self.signature_repo.mark_signer_signed(
            signer_id=signer.id,
            signature_image_base64=signature_image_base64,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Record consents in audit trail
        await self.audit_service.log_event(
            request_id=request.id,
            event_type="consent_given",
            actor_email=signer.email,
            actor_role="signer",
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "signer_id": str(signer.id),
                "identity_confirmed": consents.identity_confirmed,
                "contract_reviewed": consents.contract_reviewed,
            },
        )

        # Log signature
        await self.audit_service.log_signed(
            request_id=request.id,
            signer_email=signer.email,
            signer_name=signer.name,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Check if all signers completed
        all_signers = await self.signature_repo.get_signers_by_request(request.id)
        all_signed = all(s.signed_at is not None for s in all_signers)

        if all_signed:
            await self._handle_all_signed(request, all_signers)
            next_signer = None
        else:
            await self.signature_repo.update_request_status(
                request_id=request.id, status="in_progress"
            )
            next_signer = self._get_next_signer(signer.signing_order, all_signers)
            if next_signer:
                await self._send_next_signer_email(request, next_signer)

        logger.success(
            "Signature completed",
            signer_email=signer.email,
            all_completed=all_signed,
        )

        return {
            "success": True,
            "message": "Signature completed successfully",
            "request_id": str(request.id),
            "signer_id": str(signer.id),
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "next_signer_name": next_signer.name if next_signer else None,
            "all_completed": all_signed,
        }

    async def _handle_all_signed(self, request, all_signers: list) -> None:  # noqa: ANN001
        """Handle completion when all signers have signed."""
        await self.signature_repo.update_request_status(
            request_id=request.id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
        await self.audit_service.log_all_completed(
            request_id=request.id,
            total_signers=len(all_signers),
        )
        logger.success("All signatures completed", request_id=str(request.id))
        logger.info(
            "All signers completed. Ready for PDF processing.",
            request_id=str(request.id),
        )

    async def _send_next_signer_email(self, request, next_signer: SignatureSigner) -> None:  # noqa: ANN001
        """Send signing invitation email to the next signer."""
        logger.info("Next signer", name=next_signer.name, email=next_signer.email)
        signing_link = f"{settings.signing_base_url}/sign/{next_signer.verification_token}"

        # Build email variables from stored email_variables + defaults
        variables = dict(request.email_variables or {})
        variables.update(
            {
                "signer_name": next_signer.name,
                "signer_email": next_signer.email,
                "signing_link": signing_link,
                "sender_name": request.sender_name,
                "document_title": request.document_title,
                "unsubscribe_link": f"{settings.signing_base_url}/unsubscribe",
            }
        )

        await self.email_service.send_email(
            to_email=next_signer.email,
            to_name=next_signer.name,
            template_key="signature_request",
            variables=variables,
        )
        await self.audit_service.log_email_sent(
            request_id=request.id,
            signer_email=next_signer.email,
        )

    def _resolve_document_html(self, request) -> str:  # noqa: ANN001
        """Resolve the HTML content to display for the document."""
        if request.is_html_mode and request.document_html:
            return request.document_html
        if request.is_json_mode and request.contract_data:
            return self._render_generic_data_view(request.contract_data)
        # PDF mode: placeholder
        return (
            f'<div class="document-placeholder"><p>PDF-Dokument: {request.document_title}</p></div>'
        )

    def _get_next_signer(
        self, current_order: int, all_signers: list[SignatureSigner]
    ) -> Optional[SignatureSigner]:
        """Get next signer in order."""
        unsigned_signers = [s for s in all_signers if s.signed_at is None]

        if not unsigned_signers:
            return None

        # Sort by signing order and return first
        unsigned_signers.sort(key=lambda s: s.signing_order)
        return unsigned_signers[0]

    def _render_generic_data_view(self, data: dict) -> str:
        """Render arbitrary dict as a clean key-value HTML view."""
        rows = self._render_dict_rows(data)
        return f"""
        <div class="document-data-view">
            <dl class="data-grid">
                {rows}
            </dl>
        </div>
        <style>
            .document-data-view {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 1rem;
                color: #1f2937;
            }}
            .data-grid {{
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }}
            .data-row {{
                display: flex;
                flex-wrap: wrap;
                padding: 0.5rem 0;
                border-bottom: 1px solid #e5e7eb;
            }}
            .data-row dt {{
                width: 200px;
                flex-shrink: 0;
                color: #6b7280;
                font-size: 0.875rem;
            }}
            .data-row dd {{
                flex: 1;
                font-weight: 500;
                color: #1f2937;
                margin: 0;
            }}
            .data-section {{
                margin-top: 1rem;
                padding-top: 0.5rem;
            }}
            .data-section-title {{
                font-size: 1rem;
                font-weight: 600;
                color: #374151;
                margin-bottom: 0.5rem;
            }}
            @media (max-width: 640px) {{
                .data-row {{
                    flex-direction: column;
                }}
                .data-row dt {{
                    width: 100%;
                    margin-bottom: 0.125rem;
                }}
            }}
        </style>
        """

    def _render_dict_rows(self, data: dict, prefix: str = "") -> str:
        """Recursively render dict keys as HTML rows."""
        rows = []
        for key, value in data.items():
            label = key.replace("_", " ").title()
            if prefix:
                label = f"{prefix} - {label}"

            if isinstance(value, dict):
                rows.append(
                    f'<div class="data-section"><div class="data-section-title">{label}</div></div>'
                )
                rows.append(self._render_dict_rows(value))
            elif isinstance(value, list):
                display = ", ".join(str(v) for v in value)
                rows.append(f'<div class="data-row"><dt>{label}:</dt><dd>{display}</dd></div>')
            else:
                display = str(value) if value is not None else "-"
                rows.append(f'<div class="data-row"><dt>{label}:</dt><dd>{display}</dd></div>')
        return "\n".join(rows)
