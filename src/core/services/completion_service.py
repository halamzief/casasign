"""Signature Completion Service - PDF processing, audit trails, and webhooks.

This service handles the complete workflow after all signers have completed:
1. Process signed PDF with signature overlays (PDF mode)
   OR Generate PDF from JSON + signatures (JSON mode)
2. Embed XMP metadata for FES compliance
3. Generate and append audit trail
4. Save to local filesystem
5. Trigger webhook callback to main app
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from src.config import Settings
from src.models.signature_request import SignatureRequest, SignatureSigner

from ..audit.audit_service import AuditService
from ..pdf.audit_trail_generator import AuditTrailGenerator
from ..pdf.html_to_pdf_service import HTMLToPDFService
from ..pdf.pdf_processor import PDFProcessingError, PDFProcessor
from ..repositories.signature_repository import SignatureRepository


class CompletionService:
    """Service for handling signature completion workflow."""

    def __init__(
        self,
        signature_repo: SignatureRepository,
        audit_service: AuditService,
        pdf_processor: PDFProcessor,
        audit_trail_generator: AuditTrailGenerator,
        settings: Settings,
        html_to_pdf_service: Optional[HTMLToPDFService] = None,
    ):
        """Initialize completion service.

        Args:
            signature_repo: Signature repository
            audit_service: Audit logging service
            pdf_processor: PDF processing service
            audit_trail_generator: Audit trail generator
            settings: Application settings
            html_to_pdf_service: HTML-to-PDF service for JSON mode (optional, lazy-loaded)
        """
        self.signature_repo = signature_repo
        self.audit_service = audit_service
        self.pdf_processor = pdf_processor
        self.audit_trail_generator = audit_trail_generator
        self.settings = settings
        self._html_to_pdf_service = html_to_pdf_service

    @property
    def html_to_pdf_service(self) -> HTMLToPDFService:
        """Lazy-load HTML-to-PDF service."""
        if self._html_to_pdf_service is None:
            self._html_to_pdf_service = HTMLToPDFService()
        return self._html_to_pdf_service

    async def process_completed_request(
        self, request: SignatureRequest, signers: list[SignatureSigner]
    ) -> dict:
        """Process completed signature request.

        Args:
            request: Completed signature request
            signers: All signers with signatures

        Returns:
            Dict with completion details

        Raises:
            PDFProcessingError: If PDF processing fails
        """
        logger.info(
            f"Processing completed request {request.id}",
            extra={
                "request_id": str(request.id),
                "contract_id": str(request.contract_id),
                "document_type": request.document_type,
                "signer_count": len(signers),
            },
        )

        try:
            # Determine processing mode based on document_type
            if request.is_json_mode:
                # JSON MODE: Generate PDF from contract_data + signatures
                signed_pdf = await self._process_json_mode(request, signers)
            else:
                # PDF MODE: Load existing PDF and add signature overlays
                signed_pdf = await self._process_pdf_mode(request, signers)

            # Step 5: Generate audit trail PDF
            audit_events = await self.audit_service.get_events_for_request(request.id)
            audit_trail_pdf = self.audit_trail_generator.generate_audit_trail_pdf(
                request=request, signers=signers, audit_events=audit_events
            )

            # Step 6: Append audit trail to signed PDF
            final_pdf = self.audit_trail_generator.append_audit_trail(
                signed_pdf_bytes=signed_pdf, audit_trail_bytes=audit_trail_pdf
            )

            # Step 6b: Merge attachment PDFs (if any)
            if request.attachments:
                final_pdf = self._merge_attachments(final_pdf, request.attachments)

            # Step 7: Save to local filesystem
            file_path = self.pdf_processor.save_signed_pdf(
                request_id=str(request.id),
                contract_id=str(request.contract_id),
                pdf_bytes=final_pdf,
            )

            # Step 8: Log completion event
            await self.audit_service.log_event(
                request_id=request.id,
                event_type="pdf_generated",
                actor_email="system",
                actor_role="system",
                ip_address=None,
                user_agent=None,
                metadata={
                    "file_path": str(file_path),
                    "file_size": len(final_pdf),
                    "signer_count": len(signers),
                },
            )

            logger.success(
                f"Successfully processed request {request.id}",
                extra={
                    "request_id": str(request.id),
                    "file_path": str(file_path),
                    "file_size": len(final_pdf),
                },
            )

            # Step 9: Trigger webhook callback (if configured)
            webhook_result = None
            if request.callback_url:
                webhook_result = await self._trigger_webhook(
                    callback_url=request.callback_url,
                    request=request,
                    signers=signers,
                    file_path=file_path,
                )

            return {
                "success": True,
                "request_id": str(request.id),
                "contract_id": str(request.contract_id),
                "file_path": str(file_path),
                "file_size": len(final_pdf),
                "signer_count": len(signers),
                "webhook_result": webhook_result,
            }

        except PDFProcessingError as e:
            logger.error(
                f"PDF processing failed for request {request.id}: {e}",
                exc_info=True,
                extra={"request_id": str(request.id)},
            )
            await self.audit_service.log_event(
                request_id=request.id,
                event_type="error",
                actor_email="system",
                actor_role="system",
                ip_address=None,
                user_agent=None,
                metadata={"error": str(e)},
            )
            raise

    async def _load_original_pdf(self, document_url: str) -> bytes:
        """Load original PDF from URL or filesystem.

        Args:
            document_url: URL or path to PDF

        Returns:
            PDF as bytes
        """
        # If document_url is a local path
        if document_url.startswith("file://") or document_url.startswith("/"):
            file_path = document_url.replace("file://", "")
            with open(file_path, "rb") as f:
                return f.read()

        # If document_url is an HTTP URL
        if document_url.startswith("http://") or document_url.startswith("https://"):
            async with httpx.AsyncClient() as client:
                response = await client.get(document_url)
                response.raise_for_status()
                return response.content

        raise ValueError(f"Unsupported document URL format: {document_url}")

    async def _process_json_mode(
        self, request: SignatureRequest, signers: list[SignatureSigner]
    ) -> bytes:
        """Process JSON mode request - generate PDF from contract_data.

        Args:
            request: Signature request with contract_data
            signers: List of signers with signatures

        Returns:
            Generated PDF as bytes
        """
        logger.info(
            f"Processing JSON mode for request {request.id}",
            extra={"request_id": str(request.id)},
        )

        # Generate PDF from JSON contract data + embedded signatures
        pdf_bytes = await self.html_to_pdf_service.generate_contract_pdf(
            request=request,
            signers=signers,
        )

        # Embed XMP metadata for FES compliance
        signed_pdf = self.pdf_processor.embed_xmp_metadata(
            pdf_bytes=pdf_bytes, request=request, signers=signers
        )

        # Update pdf_generated_at timestamp
        await self.signature_repo.update_request_pdf_generated(
            request_id=request.id,
            pdf_generated_at=datetime.now(timezone.utc),
        )

        logger.success(
            f"JSON mode PDF generated for request {request.id}",
            extra={"pdf_size": len(signed_pdf)},
        )

        return signed_pdf

    async def _process_pdf_mode(
        self, request: SignatureRequest, signers: list[SignatureSigner]
    ) -> bytes:
        """Process PDF mode request - add signature overlays to existing PDF.

        Args:
            request: Signature request with document_url
            signers: List of signers with signatures

        Returns:
            Signed PDF as bytes
        """
        logger.info(
            f"Processing PDF mode for request {request.id}",
            extra={"request_id": str(request.id)},
        )

        # Step 1: Load original PDF
        original_pdf = await self._load_original_pdf(request.document_url)

        # Step 2: Validate document hash
        if not self.pdf_processor.validate_document_hash(original_pdf, request.document_hash):
            raise PDFProcessingError("Document hash validation failed - PDF has been modified")

        # Step 3: Add signature overlays for all signers
        signed_pdf = original_pdf
        for signer in signers:
            if signer.signature_image_base64:
                signed_pdf = self.pdf_processor.add_signature_overlay(
                    pdf_bytes=signed_pdf,
                    signer=signer,
                    signature_image_base64=signer.signature_image_base64,
                )
            else:
                logger.warning(
                    f"Signer {signer.name} has no signature image",
                    extra={"signer_id": str(signer.id)},
                )

        # Step 4: Embed XMP metadata
        signed_pdf = self.pdf_processor.embed_xmp_metadata(
            pdf_bytes=signed_pdf, request=request, signers=signers
        )

        return signed_pdf

    def _merge_attachments(self, contract_pdf: bytes, attachments: list[dict]) -> bytes:
        """Merge attachment PDFs into the final signed document.

        Appends each attachment PDF after the contract + audit trail.
        """
        import io

        from pypdf import PdfReader, PdfWriter

        writer = PdfWriter()

        # Add contract pages
        contract_reader = PdfReader(io.BytesIO(contract_pdf))
        for page in contract_reader.pages:
            writer.add_page(page)

        # Add attachment pages
        for att in attachments:
            try:
                att_path = Path(att["storage_path"])
                if not att_path.exists():
                    logger.warning(f"Attachment file not found: {att_path}")
                    continue
                att_reader = PdfReader(str(att_path))
                for page in att_reader.pages:
                    writer.add_page(page)
                logger.info(f"Merged attachment: {att['filename']} ({len(att_reader.pages)} pages)")
            except Exception as e:
                logger.warning(f"Failed to merge attachment {att.get('filename')}: {e}")

        # Write merged PDF
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    async def _trigger_webhook(
        self,
        callback_url: str,
        request: SignatureRequest,
        signers: list[SignatureSigner],
        file_path: Path,
    ) -> dict:
        """Trigger webhook callback to main app.

        Args:
            callback_url: Webhook URL
            request: Signature request
            signers: All signers
            file_path: Path to signed PDF

        Returns:
            Dict with webhook result
        """
        logger.info(
            f"Triggering webhook for request {request.id}",
            extra={"callback_url": callback_url, "request_id": str(request.id)},
        )

        webhook_payload = {
            "event": "signature_completed",
            "request_id": str(request.id),
            "contract_id": str(request.contract_id),
            "signed_pdf_path": str(file_path),
            "signed_pdf_url": f"{self.settings.backend_url}/api/sign/download/{request.id}",
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            "signers": [
                {
                    "name": signer.name,
                    "email": signer.email,
                    "role": signer.role,
                    "signed_at": signer.signed_at.isoformat() if signer.signed_at else None,
                    "ip_address": str(signer.ip_address) if signer.ip_address else None,
                }
                for signer in signers
            ],
        }

        try:
            # Try webhook with retries
            result = await self._send_webhook_with_retries(
                callback_url=callback_url,
                payload=webhook_payload,
                max_retries=3,
            )

            await self.audit_service.log_event(
                request_id=request.id,
                event_type="webhook_sent",
                actor_email="system",
                actor_role="system",
                ip_address=None,
                user_agent=None,
                metadata={
                    "callback_url": callback_url,
                    "status_code": result.get("status_code"),
                    "success": result.get("success"),
                },
            )

            logger.success(
                f"Webhook sent successfully for request {request.id}",
                extra={"status_code": result.get("status_code")},
            )

            return result

        except Exception as e:
            logger.error(
                f"Webhook failed for request {request.id}: {e}",
                exc_info=True,
                extra={"callback_url": callback_url},
            )
            await self.audit_service.log_event(
                request_id=request.id,
                event_type="webhook_failed",
                actor_email="system",
                actor_role="system",
                ip_address=None,
                user_agent=None,
                metadata={"callback_url": callback_url, "error": str(e)},
            )
            return {
                "success": False,
                "error": str(e),
            }

    async def _send_webhook_with_retries(
        self, callback_url: str, payload: dict, max_retries: int = 3
    ) -> dict:
        """Send webhook with exponential backoff retries.

        Args:
            callback_url: Webhook URL
            payload: Webhook payload
            max_retries: Maximum retry attempts

        Returns:
            Dict with result

        Raises:
            httpx.HTTPError: If all retries fail
        """
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(callback_url, json=payload)
                    response.raise_for_status()

                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "response": response.json() if response.content else None,
                        "attempt": attempt + 1,
                    }

            except httpx.HTTPError as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2**attempt
                    logger.warning(
                        f"Webhook attempt {attempt + 1} failed, retrying in {wait_time}s: {e}",
                        extra={"callback_url": callback_url},
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"All webhook attempts failed: {e}",
                        exc_info=True,
                        extra={"callback_url": callback_url},
                    )
                    raise

        # Should never reach here
        raise RuntimeError("Webhook retry logic failed")
