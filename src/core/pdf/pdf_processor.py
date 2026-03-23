"""PDF Processing Service - Signature Overlay & Metadata Embedding.

This module handles:
1. Adding signature overlays to PDFs using ReportLab
2. Embedding XMP metadata for FES compliance
3. SHA-256 hash validation
4. Audit trail PDF generation and appending
"""

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from src.models.signature_request import SignatureRequest, SignatureSigner
from src.utils.hash_utils import calculate_sha256 as calculate_pdf_hash


class PDFProcessingError(Exception):
    """Raised when PDF processing fails."""

    pass


class PDFProcessor:
    """Service for processing signed PDFs with signature overlays and metadata."""

    def __init__(self, storage_path: Path):
        """Initialize PDF processor.

        Args:
            storage_path: Base directory for storing signed PDFs
        """
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def add_signature_overlay(
        self,
        pdf_bytes: bytes,
        signer: SignatureSigner,
        signature_image_base64: str,
        page_number: Optional[int] = None,
    ) -> bytes:
        """Add signature overlay to PDF.

        Args:
            pdf_bytes: Original PDF as bytes
            signer: Signer information
            signature_image_base64: Base64-encoded signature image (PNG)
            page_number: Page to add signature (None = last page)

        Returns:
            PDF with signature overlay as bytes

        Raises:
            PDFProcessingError: If signature overlay fails
        """
        try:
            # Read original PDF
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
            pdf_writer = PdfWriter()

            # Determine target page
            if page_number is None:
                page_number = len(pdf_reader.pages) - 1
            elif page_number < 0 or page_number >= len(pdf_reader.pages):
                raise PDFProcessingError(
                    f"Invalid page number {page_number}. PDF has {len(pdf_reader.pages)} pages."
                )

            # Create signature overlay
            overlay_bytes = self._create_signature_overlay(
                signer=signer, signature_image_base64=signature_image_base64
            )
            overlay_reader = PdfReader(io.BytesIO(overlay_bytes))

            # Add all pages
            for idx, page in enumerate(pdf_reader.pages):
                if idx == page_number:
                    # Merge signature overlay onto target page
                    page.merge_page(overlay_reader.pages[0])
                pdf_writer.add_page(page)

            # Copy metadata
            if pdf_reader.metadata:
                for key, value in pdf_reader.metadata.items():
                    pdf_writer.add_metadata({key: value})

            # Write to bytes
            output = io.BytesIO()
            pdf_writer.write(output)
            output.seek(0)

            logger.info(
                f"Added signature overlay for {signer.name} on page {page_number + 1}",
                extra={"signer_id": str(signer.id), "signer_name": signer.name},
            )

            return output.getvalue()

        except Exception as e:
            logger.error(f"Failed to add signature overlay: {e}", exc_info=True)
            raise PDFProcessingError(f"Signature overlay failed: {e}") from e

    def _create_signature_overlay(
        self, signer: SignatureSigner, signature_image_base64: str
    ) -> bytes:
        """Create signature overlay PDF using ReportLab.

        Args:
            signer: Signer information
            signature_image_base64: Base64-encoded signature image

        Returns:
            Overlay PDF as bytes
        """
        # Decode base64 image
        import base64

        sig_data = signature_image_base64
        if "," in sig_data:
            sig_data = sig_data.split(",", 1)[1]
        image_data = base64.b64decode(sig_data)
        image = Image.open(io.BytesIO(image_data))

        # Create overlay canvas
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)

        # Signature position (bottom-right corner with margins)
        sig_width = 60 * mm
        sig_height = 30 * mm
        x_position = A4[0] - sig_width - 20 * mm
        y_position = 40 * mm

        # Save image temporarily
        temp_image = io.BytesIO()
        image.save(temp_image, format="PNG")
        temp_image.seek(0)

        # Draw signature box
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.5)
        c.rect(x_position, y_position, sig_width, sig_height)

        # Draw signature image
        c.drawImage(
            temp_image,
            x_position + 2 * mm,
            y_position + sig_height / 2,
            width=sig_width - 4 * mm,
            height=sig_height / 2 - 2 * mm,
            preserveAspectRatio=True,
            mask="auto",
        )

        # Draw signer name
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.drawString(x_position + 2 * mm, y_position + 8 * mm, signer.name)

        # Draw timestamp
        if signer.signed_at:
            timestamp_str = signer.signed_at.strftime("%d.%m.%Y %H:%M:%S")
            c.setFont("Helvetica", 7)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(x_position + 2 * mm, y_position + 3 * mm, timestamp_str)

        c.save()
        packet.seek(0)

        return packet.getvalue()

    def embed_xmp_metadata(
        self,
        pdf_bytes: bytes,
        request: SignatureRequest,
        signers: list[SignatureSigner],
    ) -> bytes:
        """Embed XMP metadata for FES compliance.

        Args:
            pdf_bytes: PDF as bytes
            request: Signature request
            signers: All signers with signatures

        Returns:
            PDF with embedded XMP metadata

        Raises:
            PDFProcessingError: If metadata embedding fails
        """
        try:
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
            pdf_writer = PdfWriter()

            # Copy all pages
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)

            # Build XMP metadata
            xmp_metadata = {
                "/SignCasa:RequestID": str(request.id),
                "/SignCasa:ContractID": str(request.contract_id),
                "/SignCasa:DocumentHash": request.document_hash,
                "/SignCasa:SignatureCount": str(len(signers)),
                "/SignCasa:CompletedAt": datetime.now(timezone.utc).isoformat(),
                "/SignCasa:FESCompliant": "true",
            }

            # Add signer metadata
            for idx, signer in enumerate(signers, start=1):
                xmp_metadata[f"/SignCasa:Signer{idx}Name"] = signer.name
                xmp_metadata[f"/SignCasa:Signer{idx}Email"] = signer.email
                xmp_metadata[f"/SignCasa:Signer{idx}Role"] = signer.role
                if signer.signed_at:
                    xmp_metadata[f"/SignCasa:Signer{idx}Timestamp"] = signer.signed_at.isoformat()
                if signer.ip_address:
                    xmp_metadata[f"/SignCasa:Signer{idx}IP"] = str(signer.ip_address)

            # Add metadata to PDF
            pdf_writer.add_metadata(xmp_metadata)

            # Write to bytes
            output = io.BytesIO()
            pdf_writer.write(output)
            output.seek(0)

            logger.info(
                f"Embedded XMP metadata for request {request.id}",
                extra={"request_id": str(request.id), "signer_count": len(signers)},
            )

            return output.getvalue()

        except Exception as e:
            logger.error(f"Failed to embed XMP metadata: {e}", exc_info=True)
            raise PDFProcessingError(f"XMP metadata embedding failed: {e}") from e

    def validate_document_hash(self, pdf_bytes: bytes, expected_hash: str) -> bool:
        """Validate PDF hash against expected hash.

        Args:
            pdf_bytes: PDF as bytes
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches, False otherwise
        """
        actual_hash = calculate_pdf_hash(pdf_bytes)
        match = actual_hash == expected_hash

        if not match:
            logger.warning(
                "Document hash mismatch",
                extra={"expected": expected_hash, "actual": actual_hash},
            )
        else:
            logger.info("Document hash validated successfully", extra={"hash": actual_hash})

        return match

    def save_signed_pdf(self, request_id: str, contract_id: str, pdf_bytes: bytes) -> Path:
        """Save signed PDF to local filesystem.

        Args:
            request_id: Signature request ID
            contract_id: Contract ID
            pdf_bytes: Final signed PDF

        Returns:
            Path to saved PDF file

        Raises:
            PDFProcessingError: If file saving fails
        """
        try:
            # Create filename: {contract_id}_{request_id}_signed.pdf
            filename = f"{contract_id}_{request_id}_signed.pdf"
            file_path = self.storage_path / filename

            # Write PDF to disk
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)

            logger.info(
                f"Saved signed PDF: {filename}",
                extra={
                    "request_id": request_id,
                    "contract_id": contract_id,
                    "file_path": str(file_path),
                    "file_size": len(pdf_bytes),
                },
            )

            return file_path

        except Exception as e:
            logger.error(f"Failed to save signed PDF: {e}", exc_info=True)
            raise PDFProcessingError(f"PDF save failed: {e}") from e
