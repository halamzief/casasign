"""Signature API endpoints."""

from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.audit.audit_service import AuditService
from src.core.email.resend_service import ResendEmailService
from src.core.email.template_service import EmailTemplateService
from src.core.repositories.email_template_repository import EmailTemplateRepository
from src.core.repositories.signature_repository import SignatureRepository
from src.core.services.signature_request_service import SignatureRequestService
from src.core.services.signing_service import SigningService
from src.database.session import get_db_session
from src.schemas.signature import (
    SignatureRequestCreate,
    SignatureRequestResponse,
    SignatureRequestStatusResponse,
)
from src.schemas.signing import (
    SignatureSubmission,
    SigningCompleteResponse,
    TokenValidationResponse,
)
from src.utils.ip_utils import get_client_ip

router = APIRouter(prefix="/api/sign", tags=["Signatures"])


@router.get("/health")
async def signature_health_check() -> dict[str, str]:
    """Health check endpoint for signature service."""
    return {
        "status": "healthy",
        "service": "signature-api",
    }


async def get_signature_service(
    session: AsyncSession = Depends(get_db_session),
) -> SignatureRequestService:
    """Dependency: Get signature request service."""
    signature_repo = SignatureRepository(session)
    email_template_repo = EmailTemplateRepository(session)

    audit_service = AuditService(session)
    template_service = EmailTemplateService(email_template_repo)
    email_service = ResendEmailService(template_service)

    return SignatureRequestService(signature_repo, audit_service, email_service)


@router.post("/request", response_model=SignatureRequestResponse, status_code=201)
async def create_signature_request(
    request_data: SignatureRequestCreate,
    request: Request,
    service: SignatureRequestService = Depends(get_signature_service),
) -> SignatureRequestResponse:
    """Create a new signature request.

    Creates a signature request with multiple signers, generates verification tokens,
    saves the PDF document, and sends email invitations to the first signer(s).

    Args:
        request_data: Signature request creation data
        request: FastAPI request object for IP extraction
        service: Signature request service dependency

    Returns:
        SignatureRequestResponse with request details and signers

    Raises:
        HTTPException: If creation fails
    """
    logger.info(
        "API: Creating signature request",
        contract_id=str(request_data.contract_id),
        signer_count=len(request_data.signers),
    )

    try:
        # Extract real client IP (supports X-Forwarded-For behind Caddy/Docker)
        ip_address: Optional[str] = get_client_ip(request)

        # Create signature request
        response = await service.create_signature_request(
            request_data=request_data,
            ip_address=ip_address,
        )

        logger.success("API: Signature request created", request_id=str(response.id))
        return response

    except ValueError as e:
        logger.error("API: Validation error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.error("API: Failed to create signature request", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create signature request") from e


@router.get("/status/{request_id}", response_model=SignatureRequestStatusResponse)
async def get_signature_status(
    request_id: UUID,
    service: SignatureRequestService = Depends(get_signature_service),
) -> SignatureRequestStatusResponse:
    """Get signature request status.

    Args:
        request_id: Signature request ID
        service: Signature request service dependency

    Returns:
        SignatureRequestStatusResponse with current status

    Raises:
        HTTPException: If request not found
    """
    logger.info("API: Getting signature status", request_id=str(request_id))

    try:
        status = await service.get_request_status(request_id)

        return SignatureRequestStatusResponse(**status)

    except ValueError as e:
        logger.error("API: Request not found", request_id=str(request_id))
        raise HTTPException(status_code=404, detail=str(e)) from e

    except Exception as e:
        logger.error("API: Failed to get signature status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get signature status") from e


@router.post("/resend/{request_id}")
async def resend_signing_emails(
    request_id: UUID,
    service: SignatureRequestService = Depends(get_signature_service),
) -> dict:
    """Resend signing emails to all unsigned signers.

    Re-sends the signing invitation email to every signer who hasn't
    signed yet. Used for the "Erneut senden" button.
    """
    logger.info("API: Resending signing emails", request_id=str(request_id))

    try:
        resent = await service.resend_signing_emails(request_id)
        return {"success": True, "resent_count": resent}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("API: Failed to resend", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to resend signing emails") from e


async def get_signing_service(
    session: AsyncSession = Depends(get_db_session),
) -> SigningService:
    """Dependency: Get signing service."""
    signature_repo = SignatureRepository(session)
    email_template_repo = EmailTemplateRepository(session)
    audit_service = AuditService(session)
    template_service = EmailTemplateService(email_template_repo)
    email_service = ResendEmailService(template_service)

    return SigningService(signature_repo, audit_service, email_service)


@router.get("/{token}", response_model=TokenValidationResponse)
async def validate_token_and_get_contract(
    token: str,
    request: Request,
    service: SigningService = Depends(get_signing_service),
) -> TokenValidationResponse:
    """Validate signing token and return contract data.

    This endpoint is called when a signer clicks the magic link in their email.
    Returns all data needed to display the contract and consent modal.

    Args:
        token: Verification token from email link
        request: FastAPI request for IP extraction
        service: Signing service dependency

    Returns:
        TokenValidationResponse with contract HTML and signer details

    Raises:
        HTTPException: If token invalid or expired
    """
    logger.info("API: Validating token", token=token[:10] + "...")

    try:
        ip_address: Optional[str] = get_client_ip(request)
        user_agent: Optional[str] = request.headers.get("user-agent")

        response = await service.validate_token_and_get_contract(
            token=token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Re-render contract HTML using polished Jinja2 template if contract_data exists
        if response.contract_data and hasattr(request.app.state, "templates"):
            try:
                template_env = request.app.state.templates.env
                template = template_env.get_template("partials/contract_polished.html")
                polished_html = await template.render_async(contract_data=response.contract_data)
                response.contract_html = polished_html
            except Exception as tmpl_err:
                import traceback

                logger.warning(
                    "Failed to render polished template, using fallback",
                    error=str(tmpl_err),
                    tb=traceback.format_exc()[-500:],
                )

        logger.success("API: Token validated", signer_email=response.signer_email)
        return response

    except ValueError as e:
        logger.error("API: Token validation failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.error("API: Failed to validate token", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to validate signing link") from e


@router.post("/{token}/complete", response_model=SigningCompleteResponse)
async def complete_signature(
    token: str,
    submission: SignatureSubmission,
    request: Request,
    service: SigningService = Depends(get_signing_service),
) -> SigningCompleteResponse:
    """Complete signature with consent and signature image.

    Args:
        token: Verification token
        submission: Signature and consent data
        request: FastAPI request for IP extraction
        service: Signing service dependency

    Returns:
        SigningCompleteResponse with completion status

    Raises:
        HTTPException: If submission fails
    """
    logger.info("API: Completing signature", token=token[:10] + "...")

    try:
        ip_address: str = get_client_ip(request)
        user_agent: str = request.headers.get("user-agent", "unknown")

        result = await service.complete_signature(
            token=token,
            signature_image_base64=submission.signature_image_base64,
            consents=submission.consents,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.success("API: Signature completed")
        return SigningCompleteResponse(**result)

    except ValueError as e:
        logger.error("API: Signature completion failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.error("API: Failed to complete signature", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to complete signature") from e


@router.post("/process-completed/{request_id}", status_code=200)
async def process_completed_request(
    request_id: UUID,
    service: SignatureRequestService = Depends(get_signature_service),
) -> dict:
    """Process completed signature request (PDF generation, audit trail, webhook).

    Args:
        request_id: Signature request ID
        service: Signature request service

    Returns:
        Dict with processing result

    Raises:
        HTTPException: If processing fails
    """
    logger.info(f"API: Processing completed request {request_id}")

    try:
        from src.core.pdf.audit_trail_generator import AuditTrailGenerator
        from src.core.pdf.pdf_processor import PDFProcessor
        from src.core.services.completion_service import CompletionService

        # Get request and signers
        request = await service.signature_repo.get_request_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Signature request not found")

        if request.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Request status is {request.status}, expected 'completed'",
            )

        signers = await service.signature_repo.get_signers_by_request(request_id)

        # Initialize completion service
        storage_path = Path(settings.signatures_storage_path)
        pdf_processor = PDFProcessor(storage_path=storage_path)
        audit_trail_generator = AuditTrailGenerator()
        completion_service = CompletionService(
            signature_repo=service.signature_repo,
            audit_service=service.audit_service,
            pdf_processor=pdf_processor,
            audit_trail_generator=audit_trail_generator,
            settings=settings,
        )

        # Process completion
        result = await completion_service.process_completed_request(
            request=request, signers=signers
        )

        logger.success(f"API: Successfully processed request {request_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Failed to process completed request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}") from e


@router.get("/download/{request_id}")
async def download_signed_pdf(
    request_id: UUID,
    service: SignatureRequestService = Depends(get_signature_service),
) -> dict:
    """Get download URL for signed PDF.

    Args:
        request_id: Signature request ID
        service: Signature request service

    Returns:
        Dict with PDF file path and metadata

    Raises:
        HTTPException: If PDF not found
    """
    logger.info(f"API: Getting download URL for request {request_id}")

    try:
        # Get request
        request = await service.signature_repo.get_request_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Signature request not found")

        if request.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Request not completed yet (status: {request.status})",
            )

        # Find signed PDF
        storage_path = Path(settings.signatures_storage_path)
        filename = f"{request.contract_id}_{request_id}_signed.pdf"
        file_path = storage_path / filename

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Signed PDF not found. Processing may not be complete.",
            )

        # Get file info
        file_size = file_path.stat().st_size
        signers = await service.signature_repo.get_signers_by_request(request_id)

        logger.success(f"API: Found signed PDF for request {request_id}")

        return {
            "success": True,
            "request_id": str(request_id),
            "contract_id": str(request.contract_id),
            "file_path": str(file_path),
            "file_size": file_size,
            "signer_count": len(signers),
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            # For production, return a secure download URL instead of file path
            # "download_url": f"{base_url}/api/sign/pdf/{request_id}/download"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Failed to get PDF download URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get PDF: {str(e)}") from e


@router.get("/download/{request_id}/file")
async def download_signed_pdf_file(
    request_id: UUID,
    service: SignatureRequestService = Depends(get_signature_service),
) -> FileResponse:
    """Download the actual signed PDF file.

    Args:
        request_id: Signature request ID
        service: Signature request service

    Returns:
        FileResponse with PDF file

    Raises:
        HTTPException: If PDF not found
    """
    logger.info(f"API: Downloading PDF file for request {request_id}")

    try:
        # Get request
        request = await service.signature_repo.get_request_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Signature request not found")

        if request.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Request not completed yet (status: {request.status})",
            )

        # Find signed PDF
        storage_path = Path(settings.signatures_storage_path)
        filename = f"{request.contract_id}_{request_id}_signed.pdf"
        file_path = storage_path / filename

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Signed PDF not found. Processing may not be complete.",
            )

        logger.success(f"API: Serving PDF file for request {request_id}")

        # Return file as download
        return FileResponse(
            path=str(file_path),
            media_type="application/pdf",
            filename=f"Mietvertrag_{request.contract_id}_signed.pdf",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Failed to download PDF file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to download PDF: {str(e)}") from e
