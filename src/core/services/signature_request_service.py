"""Signature request service - business logic orchestration."""

from typing import Optional
from uuid import UUID

from loguru import logger

from src.config import settings
from src.core.audit.audit_service import AuditService
from src.core.email.resend_service import ResendEmailService
from src.core.repositories.signature_repository import SignatureRepository
from src.models.signature_request import SignatureRequest, SignatureSigner
from src.schemas.signature import SignatureRequestCreate, SignatureRequestResponse, SignerResponse


class SignatureRequestService:
    """Service for managing signature requests."""

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

    async def create_signature_request(
        self,
        request_data: SignatureRequestCreate,
        ip_address: Optional[str] = None,
    ) -> SignatureRequestResponse:
        """Create signature request and send emails to first signer(s).

        Supports three modes:
        - PDF mode: request_data.document_pdf_base64 is provided
        - JSON mode: request_data.contract_data is provided
        - HTML mode: request_data.document_html is provided

        Args:
            request_data: Signature request creation data
            ip_address: Optional IP address of requester

        Returns:
            SignatureRequestResponse with created request and signers
        """
        document_type = request_data.document_type

        logger.info(
            "Creating signature request",
            contract_id=str(request_data.contract_id),
            document_type=document_type,
            signer_count=len(request_data.signers),
        )

        try:
            # Prepare contract_data dict if in JSON mode
            contract_data_dict = None
            if document_type == "json" and request_data.contract_data:
                contract_data_dict = request_data.contract_data

            # Create request and signers in database
            request, signers = await self.signature_repo.create_request(
                contract_id=request_data.contract_id,
                requester_user_id=request_data.requester_user_id,
                requester_email=request_data.requester_email,
                tenant_id=request_data.tenant_id,
                signers=request_data.signers,
                # PDF mode
                document_pdf_base64=request_data.document_pdf_base64,
                # JSON mode
                contract_data=contract_data_dict,
                # HTML mode
                document_html=request_data.document_html,
                # Generic metadata
                document_title=request_data.document_title,
                document_name=request_data.document_name,
                sender_name=request_data.sender_name,
                email_variables=request_data.email_variables,
                callback_url=request_data.callback_url,
                custom_email_template_id=request_data.custom_email_template_id,
                expires_in_days=request_data.expires_in_days,
            )

            # Log audit event
            await self.audit_service.log_request_created(
                request_id=request.id,
                requester_email=request.requester_email,
                signer_count=len(signers),
                ip_address=ip_address,
            )

            # Send emails to first signer(s) in order
            first_order = min(signer.signing_order for signer in signers)
            first_signers = [s for s in signers if s.signing_order == first_order]

            for signer in first_signers:
                await self._send_signature_request_email(request, signer)

            logger.success(
                "Signature request created successfully",
                request_id=str(request.id),
                document_type=document_type,
                emails_sent=len(first_signers),
            )

            # Build response
            return self._build_response(request, signers)

        except Exception as e:
            logger.error(f"Failed to create signature request: {e!s}")
            raise

    async def _send_signature_request_email(
        self,
        request: SignatureRequest,
        signer: SignatureSigner,
    ) -> None:
        """Send signature request email to signer."""
        signing_link = f"{settings.signing_base_url}/sign/{signer.verification_token}"

        logger.info(
            "Sending signature request email",
            signer_email=signer.email,
            signing_link=signing_link,
        )

        # Build variables from stored email_variables + defaults
        variables = dict(request.email_variables or {})
        variables.update(
            {
                "signer_name": signer.name,
                "signer_email": signer.email,
                "signing_link": signing_link,
                "sender_name": request.sender_name,
                "document_title": request.document_title,
                "unsubscribe_link": f"{settings.signing_base_url}/unsubscribe",
            }
        )

        result = await self.email_service.send_email(
            to_email=signer.email,
            to_name=signer.name,
            template_key="signature_request",
            variables=variables,
        )

        # Log audit event
        await self.audit_service.log_email_sent(
            request_id=request.id,
            signer_email=signer.email,
            email_id=result.email_id,
        )

        if not result.success:
            logger.error("Failed to send email", signer_email=signer.email, error=result.message)
            await self.audit_service.log_error(
                request_id=request.id,
                error_message=f"Failed to send email to {signer.email}",
                error_context={"email_result": result.message},
            )

    async def get_request_status(self, request_id: UUID) -> dict:
        """Get signature request status.

        Args:
            request_id: Signature request ID

        Returns:
            Status dictionary with progress information
        """
        request = await self.signature_repo.get_request_by_id(request_id)

        if not request:
            raise ValueError(f"Signature request not found: {request_id}")

        signers = await self.signature_repo.get_signers_by_request(request_id)

        signed_count = sum(1 for s in signers if s.signed_at is not None)
        pending_signers = [s.name for s in signers if s.signed_at is None]

        return {
            "id": str(request.id),
            "status": request.status,
            "total_signers": len(signers),
            "signed_count": signed_count,
            "pending_signers": pending_signers,
            "expires_at": request.expires_at,
            "created_at": request.created_at,
            "completed_at": request.completed_at,
        }

    def _build_response(
        self,
        request: SignatureRequest,
        signers: list[SignatureSigner],
    ) -> SignatureRequestResponse:
        """Build API response."""
        signer_responses = [
            SignerResponse(
                id=signer.id,
                name=signer.name,
                email=signer.email,
                phone=signer.phone,
                role=signer.role,
                signing_order=signer.signing_order,
                verification_method=signer.verification_method,
                signed_at=signer.signed_at,
                signing_link=(
                    f"{settings.signing_base_url}/sign/{signer.verification_token}"
                    if signer.signed_at is None
                    else None
                ),
            )
            for signer in signers
        ]

        return SignatureRequestResponse(
            id=request.id,
            contract_id=request.contract_id,
            document_hash=request.document_hash,
            document_type=request.document_type,
            status=request.status,
            signers=signer_responses,
            expires_at=request.expires_at,
            created_at=request.created_at,
            completed_at=request.completed_at,
        )
