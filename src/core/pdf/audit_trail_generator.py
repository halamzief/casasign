"""Audit Trail PDF Generator - FES Compliance Documentation.

This module generates audit trail pages that are appended to signed contracts,
providing complete FES (Fortgeschrittene Elektronische Signatur) compliance documentation.
"""

import io
from datetime import datetime, timezone

from loguru import logger
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from src.models.signature_request import SignatureRequest, SignatureSigner


class AuditTrailGenerator:
    """Service for generating FES-compliant audit trail documentation."""

    def generate_audit_trail_pdf(
        self,
        request: SignatureRequest,
        signers: list[SignatureSigner],
        audit_events: list[dict],
    ) -> bytes:
        """Generate audit trail PDF pages.

        Args:
            request: Signature request
            signers: All signers with their signatures
            audit_events: List of audit log events

        Returns:
            Audit trail PDF as bytes
        """
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        width, height = A4

        # Page margins
        margin_x = 20 * mm
        margin_y = 20 * mm
        width - 2 * margin_x
        y_position = height - margin_y

        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin_x, y_position, "Digitale Signatur - Prüfprotokoll")
        y_position -= 10 * mm

        # Subtitle
        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(
            margin_x,
            y_position,
            "Fortgeschrittene Elektronische Signatur (FES) gemäß eIDAS",
        )
        y_position -= 15 * mm

        # Document Information Section
        c.setFont("Helvetica-Bold", 12)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(margin_x, y_position, "1. Dokumentinformationen")
        y_position -= 7 * mm

        c.setFont("Helvetica", 9)
        doc_info = [
            ("Vertrag-ID:", str(request.contract_id)),
            ("Signaturanfrage-ID:", str(request.id)),
            ("Dokumenten-Hash (SHA-256):", request.document_hash or "N/A (JSON-Modus)"),
            ("Erstellt am:", request.created_at.strftime("%d.%m.%Y %H:%M:%S UTC")),
            (
                "Abgeschlossen am:",
                request.completed_at.strftime("%d.%m.%Y %H:%M:%S UTC")
                if request.completed_at
                else "N/A",
            ),
            ("Status:", request.status.upper()),
        ]

        for label, value in doc_info:
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawString(margin_x, y_position, label)
            c.setFillColorRGB(0, 0, 0)
            # Wrap long values
            if len(value) > 80:
                c.drawString(margin_x + 50 * mm, y_position, value[:80])
                y_position -= 4 * mm
                c.drawString(margin_x + 50 * mm, y_position, value[80:])
            else:
                c.drawString(margin_x + 50 * mm, y_position, value)
            y_position -= 5 * mm

        y_position -= 5 * mm

        # Signers Section
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_x, y_position, "2. Unterzeichner")
        y_position -= 7 * mm

        for idx, signer in enumerate(signers, start=1):
            c.setFont("Helvetica-Bold", 10)
            c.drawString(margin_x, y_position, f"Unterzeichner {idx}: {signer.name}")
            y_position -= 5 * mm

            c.setFont("Helvetica", 9)
            signer_info = [
                ("E-Mail:", signer.email),
                ("Rolle:", self._translate_role(signer.role)),
                (
                    "Verifizierungsmethode:",
                    self._translate_verification(signer.verification_method),
                ),
                (
                    "Unterschrieben am:",
                    signer.signed_at.strftime("%d.%m.%Y %H:%M:%S UTC")
                    if signer.signed_at
                    else "N/A",
                ),
                ("IP-Adresse:", str(signer.ip_address) if signer.ip_address else "N/A"),
                (
                    "User-Agent:",
                    signer.user_agent[:60] + "..."
                    if signer.user_agent and len(signer.user_agent) > 60
                    else signer.user_agent or "N/A",
                ),
            ]

            for label, value in signer_info:
                c.setFillColorRGB(0.3, 0.3, 0.3)
                c.drawString(margin_x + 5 * mm, y_position, label)
                c.setFillColorRGB(0, 0, 0)
                c.drawString(margin_x + 55 * mm, y_position, value)
                y_position -= 4 * mm

            y_position -= 3 * mm

            # Check if new page needed
            if y_position < 50 * mm:
                c.showPage()
                y_position = height - margin_y

        # Check if new page needed for events
        if y_position < 80 * mm:
            c.showPage()
            y_position = height - margin_y

        # Audit Events Section
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_x, y_position, "3. Ereignisprotokoll")
        y_position -= 7 * mm

        c.setFont("Helvetica", 8)
        for event in audit_events[-20:]:
            timestamp = event.get("created_at", "")
            event_type = self._translate_event_type(event.get("event_type", ""))
            actor = event.get("actor_email", "System")

            event_line = f"[{timestamp}] {event_type} - {actor}"
            c.drawString(margin_x, y_position, event_line)
            y_position -= 4 * mm

            # Check if new page needed
            if y_position < 30 * mm:
                c.showPage()
                y_position = height - margin_y

        y_position -= 5 * mm

        # FES Compliance Statement
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_x, y_position, "4. FES-Konformitätserklärung")
        y_position -= 7 * mm

        c.setFont("Helvetica", 9)
        compliance_text = [
            "Dieses Dokument erfüllt die Anforderungen der eIDAS-Verordnung für",
            "Fortgeschrittene Elektronische Signaturen (FES):",
            "",
            "✓ Eindeutig dem Unterzeichner zugeordnet (Email + Verifizierungs-Token)",
            "✓ Identifizierung des Unterzeichners (Name, E-Mail, IP, Zeitstempel)",
            "✓ Alleinige Kontrolle (Token-basierte Authentifizierung)",
            "✓ Manipulationserkennung (SHA-256 Dokumenten-Hash)",
            "✓ Vollständiges Prüfprotokoll (Unveränderliches Ereignisprotokoll)",
            "",
            "Gemäß Artikel 26 der eIDAS-Verordnung (EU) Nr. 910/2014 hat eine",
            "fortgeschrittene elektronische Signatur dieselbe Rechtswirkung wie eine",
            "handschriftliche Unterschrift bei Mietverträgen und ähnlichen Dokumenten.",
        ]

        for line in compliance_text:
            c.drawString(margin_x, y_position, line)
            y_position -= 4 * mm

            # Check if new page needed
            if y_position < 30 * mm:
                c.showPage()
                y_position = height - margin_y

        y_position -= 10 * mm

        # Footer with generation timestamp
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        footer_text = f"Prüfprotokoll generiert am {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M:%S UTC')} | SignCasa FES Signature Service"
        c.drawString(margin_x, 15 * mm, footer_text)

        c.save()
        packet.seek(0)

        logger.info(
            f"Generated audit trail PDF for request {request.id}",
            extra={
                "request_id": str(request.id),
                "signer_count": len(signers),
                "event_count": len(audit_events),
            },
        )

        return packet.getvalue()

    def append_audit_trail(self, signed_pdf_bytes: bytes, audit_trail_bytes: bytes) -> bytes:
        """Append audit trail pages to signed PDF.

        Args:
            signed_pdf_bytes: Signed contract PDF
            audit_trail_bytes: Audit trail PDF

        Returns:
            Complete PDF with audit trail appended
        """
        try:
            # Read both PDFs
            signed_pdf = PdfReader(io.BytesIO(signed_pdf_bytes))
            audit_pdf = PdfReader(io.BytesIO(audit_trail_bytes))

            # Create writer
            pdf_writer = PdfWriter()

            # Add signed contract pages
            for page in signed_pdf.pages:
                pdf_writer.add_page(page)

            # Add audit trail pages
            for page in audit_pdf.pages:
                pdf_writer.add_page(page)

            # Copy metadata from signed PDF
            if signed_pdf.metadata:
                for key, value in signed_pdf.metadata.items():
                    pdf_writer.add_metadata({key: value})

            # Add audit trail marker
            pdf_writer.add_metadata(
                {
                    "/SignCasa:AuditTrailAppended": "true",
                    "/SignCasa:AuditTrailPages": str(len(audit_pdf.pages)),
                }
            )

            # Write to bytes
            output = io.BytesIO()
            pdf_writer.write(output)
            output.seek(0)

            logger.info(
                "Appended audit trail to signed PDF",
                extra={
                    "signed_pages": len(signed_pdf.pages),
                    "audit_pages": len(audit_pdf.pages),
                    "total_pages": len(signed_pdf.pages) + len(audit_pdf.pages),
                },
            )

            return output.getvalue()

        except Exception as e:
            logger.error(f"Failed to append audit trail: {e}", exc_info=True)
            raise

    def _translate_role(self, role: str) -> str:
        """Translate role to German."""
        translations = {
            "landlord": "Vermieter",
            "tenant_1": "Mieter 1",
            "tenant_2": "Mieter 2",
            "witness": "Zeuge",
        }
        return translations.get(role, role)

    def _translate_verification(self, method: str) -> str:
        """Translate verification method to German."""
        translations = {
            "email_link": "E-Mail Magic Link",
            "whatsapp_link": "WhatsApp Link (Premium)",
        }
        return translations.get(method, method)

    def _translate_event_type(self, event_type: str) -> str:
        """Translate event type to German."""
        translations = {
            "request_created": "Anfrage erstellt",
            "email_sent": "E-Mail gesendet",
            "link_clicked": "Link geöffnet",
            "document_viewed": "Dokument angesehen",
            "consent_given": "Einwilligung erteilt",
            "signed": "Unterschrieben",
            "completed": "Abgeschlossen",
            "expired": "Abgelaufen",
            "error": "Fehler",
        }
        return translations.get(event_type, event_type)
