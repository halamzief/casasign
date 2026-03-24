"""Signing flow service - handles token validation and signature completion."""

from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from src.config import settings
from src.core.audit.audit_service import AuditService
from src.core.email.resend_service import ResendEmailService
from src.core.repositories.signature_repository import SignatureRepository
from src.core.services.webhook_helpers import send_webhook_with_retries
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
        """Validate signing token and return contract data.

        Args:
            token: Verification token from email link
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            TokenValidationResponse with contract and signer data

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

        # Check if expired
        if (
            request.expires_at
            and datetime.fromisoformat(str(request.expires_at)).replace(tzinfo=timezone.utc)
            < datetime.now(timezone.utc)
        ):
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

        # Generate contract HTML based on document type
        if request.document_type == "html" and request.document_html:
            # HTML mode: Use pre-rendered HTML from caller
            contract_html = request.document_html
            contract_data = None
            property_address = request.document_title or ""
            landlord_name = request.sender_name or "Vermieter"
        elif request.is_json_mode and request.contract_data:
            # JSON mode: Render HTML from contract data
            contract_html = self._render_html_from_contract_data(request.contract_data)
            contract_data = request.contract_data
            # Extract display fields from contract data
            property_address = self._get_property_address(request.contract_data)
            landlord_name = request.contract_data.get("vermieter", {}).get("name", "Vermieter")
        else:
            # PDF mode: Use placeholder HTML (PDF will be shown)
            contract_html = self._generate_contract_html(request, signer)
            contract_data = None
            property_address = ""
            landlord_name = "Vermieter"

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
            property_address=property_address,
            landlord_name=landlord_name,
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
            consents: GDPR consents
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
            raise ValueError("Contract already signed")

        # Get request
        request = await self.signature_repo.get_request_by_id(signer.request_id)

        if not request:
            raise ValueError("Signature request not found")

        # Mark signer as signed with consents
        await self.signature_repo.mark_signer_signed(
            signer_id=signer.id,
            signature_image_base64=signature_image_base64,
            ip_address=ip_address,
            user_agent=user_agent,
            consents=consents.model_dump() if consents else None,
        )

        # Record GDPR consents in audit trail
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
            # Update request status to completed
            await self.signature_repo.update_request_status(
                request_id=request.id,
                status="completed",
                completed_at=datetime.now(timezone.utc),
            )

            # Log completion
            await self.audit_service.log_all_completed(
                request_id=request.id,
                total_signers=len(all_signers),
            )

            logger.success("All signatures completed", request_id=str(request.id))

            # Send signer_signed webhook for the final signer
            await self._send_signer_webhook(request, signer, all_signers)

            # Trigger completion service (PDF generation + signature_completed webhook)
            await self._trigger_completion(request, all_signers)

            next_signer = None
        else:
            # Update to in_progress
            await self.signature_repo.update_request_status(
                request_id=request.id,
                status="in_progress",
            )

            # Send signer_signed webhook for intermediate signers
            await self._send_signer_webhook(request, signer, all_signers)

            # Get next signer
            next_signer = self._get_next_signer(signer.signing_order, all_signers)

            if next_signer:
                logger.info("Next signer", name=next_signer.name, email=next_signer.email)
                # Send email to next signer
                signing_link = f"{settings.signing_base_url}/sign/{next_signer.verification_token}"

                # Extract data from contract_data if available
                contract_data = request.contract_data or {}
                landlord_name = contract_data.get("vermieter", {}).get("name", "Vermieter")
                mietobjekt = contract_data.get("mietobjekt", {})
                property_address = (
                    f"{mietobjekt.get('strasse', '')} {mietobjekt.get('hausnummer', '')}, "
                    f"{mietobjekt.get('plz', '')} {mietobjekt.get('ort', '')}"
                ).strip(", ") if mietobjekt else ""
                kaution_amount = contract_data.get("kaution", {}).get("betrag", 0.0)

                await self.email_service.send_signature_request(
                    signer_email=next_signer.email,
                    signer_name=next_signer.name,
                    landlord_name=landlord_name,
                    property_address=property_address,
                    signing_link=signing_link,
                    kaution_amount=kaution_amount,
                )
                # Log email sent
                await self.audit_service.log_email_sent(
                    request_id=request.id,
                    signer_email=next_signer.email,
                )

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

    async def _send_signer_webhook(
        self,
        request: Any,
        signer: SignatureSigner,
        all_signers: list[SignatureSigner],
    ) -> None:
        """Send signer_signed webhook to callback_url if configured."""
        if not request.callback_url:
            return
        payload = {
            "event": "signer_signed",
            "request_id": str(request.id),
            "contract_id": str(request.contract_id),
            "signer": {
                "name": signer.name,
                "email": signer.email,
                "role": signer.role,
                "signed_at": datetime.now(timezone.utc).isoformat(),
            },
            "signers": [
                {
                    "email": s.email,
                    "name": s.name,
                    "role": s.role,
                    "status": "signed" if s.signed_at else "pending",
                }
                for s in all_signers
            ],
        }
        try:
            await send_webhook_with_retries(
                callback_url=request.callback_url,
                payload=payload,
                webhook_secret=settings.webhook_secret or None,
            )
            logger.info(f"signer_signed webhook sent for {signer.email}")
        except Exception as e:
            logger.error(f"signer_signed webhook failed: {e}")

    async def _trigger_completion(
        self,
        request: Any,
        all_signers: list[SignatureSigner],
    ) -> None:
        """Trigger PDF generation + signature_completed webhook."""
        from pathlib import Path

        from src.core.pdf.audit_trail_generator import AuditTrailGenerator
        from src.core.pdf.pdf_processor import PDFProcessor

        from .completion_service import CompletionService

        try:
            storage_path = Path(settings.signatures_storage_path)
            pdf_processor = PDFProcessor(storage_path=storage_path)
            audit_trail_generator = AuditTrailGenerator()
            completion_service = CompletionService(
                signature_repo=self.signature_repo,
                audit_service=self.audit_service,
                pdf_processor=pdf_processor,
                audit_trail_generator=audit_trail_generator,
                settings=settings,
            )
            result = await completion_service.process_completed_request(
                request=request, signers=all_signers
            )
            logger.success(f"Completion processed: {result.get('file_path')}")
        except Exception as e:
            logger.error(f"Completion service failed: {e}", exc_info=True)

    def _generate_contract_html(self, request, signer: SignatureSigner) -> str:
        """Generate contract HTML from template.

        TODO: In production, use proper contract template rendering.
        """
        return f"""
        <div class="contract-document">
            <h1 class="text-2xl font-bold mb-4">Mietvertrag</h1>

            <section class="mb-6">
                <h2 class="text-xl font-semibold mb-2">Vertragsparteien</h2>
                <p><strong>Vermieter:</strong> Max Mustermann</p>
                <p><strong>Mieter:</strong> {signer.name}</p>
            </section>

            <section class="mb-6">
                <h2 class="text-xl font-semibold mb-2">Mietobjekt</h2>
                <p>Musterstraße 123</p>
                <p>10115 Berlin</p>
            </section>

            <section class="mb-6">
                <h2 class="text-xl font-semibold mb-2">Mietkonditionen</h2>
                <p><strong>Kaltmiete:</strong> 1.200,00 €</p>
                <p><strong>Nebenkosten:</strong> 200,00 €</p>
                <p><strong>Kaution:</strong> 3.600,00 €</p>
            </section>

            <section class="mb-6">
                <h2 class="text-xl font-semibold mb-2">Mietbeginn</h2>
                <p>01.01.2025</p>
            </section>

            <section class="mb-6">
                <h2 class="text-xl font-semibold mb-2">Allgemeine Geschäftsbedingungen</h2>
                <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
            </section>
        </div>
        """

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

    def _get_property_address(self, contract_data: dict) -> str:
        """Extract property address from contract data."""
        mietobjekt = contract_data.get("mietobjekt", {})
        strasse = mietobjekt.get("strasse", "")
        hausnummer = mietobjekt.get("hausnummer", "")
        plz = mietobjekt.get("plz", "")
        ort = mietobjekt.get("ort", "")

        if strasse and plz and ort:
            return f"{strasse} {hausnummer}, {plz} {ort}"
        return "Adresse nicht verfügbar"

    def _format_date(self, date_str: Optional[str]) -> str:
        """Format date string from YYYY-MM-DD to DD.MM.YYYY."""
        if not date_str:
            return "-"
        try:
            from datetime import datetime

            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            return date_str

    def _format_currency(self, amount: Optional[float]) -> str:
        """Format amount as German currency."""
        if amount is None:
            return "-"
        return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    def _render_html_from_contract_data(self, contract_data: dict) -> str:
        """Render HTML contract from JSON data.

        This generates a mobile-optimized HTML view of the contract
        that replaces the slow PDF rendering.
        """
        # Extract data
        vermieter = contract_data.get("vermieter", {})
        mieter1 = contract_data.get("mieter1", {})
        mieter2 = contract_data.get("mieter2")
        mietobjekt = contract_data.get("mietobjekt", {})
        mietzeit = contract_data.get("mietzeit", {})
        miete = contract_data.get("miete", {})
        kaution = contract_data.get("kaution", {})
        bankverbindung = contract_data.get("bankverbindung", {})
        vereinbarungen = contract_data.get("vereinbarungen", {})
        metadata = contract_data.get("metadata", {})

        # Format address helper
        def format_address(addr: Optional[dict]) -> str:
            if not addr:
                return "-"
            return f"{addr.get('strasse', '')} {addr.get('hausnummer', '')}, {addr.get('plz', '')} {addr.get('stadt', '')}"

        # Build HTML
        html = f"""
        <div class="contract-document">
            <header class="contract-header">
                <h1>Mietvertrag über Wohnraum</h1>
                <p class="contract-subtitle">nach den Vorschriften des Bürgerlichen Gesetzbuches</p>
                {f'<p class="contract-number">Nr. {metadata.get("contract_number", "-")}</p>' if metadata.get("contract_number") else ""}
            </header>

            <section class="contract-section">
                <h2>§ 1 VERMIETER</h2>
                <dl class="info-grid">
                    <div class="info-row"><dt>Name/Firma:</dt><dd>{vermieter.get("name", "-")}</dd></div>
                    <div class="info-row"><dt>E-Mail:</dt><dd>{vermieter.get("email", "-")}</dd></div>
                    {f'<div class="info-row"><dt>Telefon:</dt><dd>{vermieter.get("phone")}</dd></div>' if vermieter.get("phone") else ""}
                    {f'<div class="info-row"><dt>Anschrift:</dt><dd>{vermieter.get("anschrift")}</dd></div>' if vermieter.get("anschrift") else ""}
                </dl>
            </section>

            <section class="contract-section">
                <h2>§ 2 MIETER</h2>
                <h3>Mieter 1 (Hauptmieter):</h3>
                <dl class="info-grid">
                    <div class="info-row"><dt>Name:</dt><dd>{mieter1.get("vorname", "")} {mieter1.get("nachname", "")}</dd></div>
                    <div class="info-row"><dt>Geburtsdatum:</dt><dd>{self._format_date(mieter1.get("geburtstag"))}</dd></div>
                    <div class="info-row"><dt>E-Mail:</dt><dd>{mieter1.get("email", "-")}</dd></div>
                    {f'<div class="info-row"><dt>Telefon:</dt><dd>{mieter1.get("telefon")}</dd></div>' if mieter1.get("telefon") else ""}
                    <div class="info-row"><dt>Anschrift:</dt><dd>{format_address(mieter1.get("anschrift"))}</dd></div>
                </dl>
        """

        # Add Mieter 2 if present
        if mieter2:
            html += f"""
                <h3>Mieter 2:</h3>
                <dl class="info-grid">
                    <div class="info-row"><dt>Name:</dt><dd>{mieter2.get("vorname", "")} {mieter2.get("nachname", "")}</dd></div>
                    <div class="info-row"><dt>Geburtsdatum:</dt><dd>{self._format_date(mieter2.get("geburtstag"))}</dd></div>
                    <div class="info-row"><dt>E-Mail:</dt><dd>{mieter2.get("email", "-")}</dd></div>
                    {f'<div class="info-row"><dt>Telefon:</dt><dd>{mieter2.get("telefon")}</dd></div>' if mieter2.get("telefon") else ""}
                </dl>
            """

        html += """
            </section>
        """

        # Mietobjekt section
        property_address = f"{mietobjekt.get('strasse', '')} {mietobjekt.get('hausnummer', '')}, {mietobjekt.get('plz', '')} {mietobjekt.get('ort', '')}"
        html += f"""
            <section class="contract-section">
                <h2>§ 3 MIETOBJEKT</h2>
                <dl class="info-grid">
                    {f'<div class="info-row"><dt>Liegenschaft:</dt><dd>{mietobjekt.get("liegenschaft")}</dd></div>' if mietobjekt.get("liegenschaft") else ""}
                    <div class="info-row"><dt>Adresse:</dt><dd>{property_address}</dd></div>
                    {f'<div class="info-row"><dt>Lage/Etage:</dt><dd>{mietobjekt.get("lage")}</dd></div>' if mietobjekt.get("lage") else ""}
                    {f'<div class="info-row"><dt>Zimmeranzahl:</dt><dd>{mietobjekt.get("zimmer_anzahl")}</dd></div>' if mietobjekt.get("zimmer_anzahl") else ""}
                    {f'<div class="info-row"><dt>Personenanzahl:</dt><dd>{mietobjekt.get("personenanzahl")}</dd></div>' if mietobjekt.get("personenanzahl") else ""}
                    {f'<div class="info-row"><dt>Kellerraum:</dt><dd>Nr. {mietobjekt.get("kellerraum_nummer")}</dd></div>' if mietobjekt.get("kellerraum_nummer") else ""}
                </dl>
            </section>

            <section class="contract-section">
                <h2>§ 4 MIETZEIT</h2>
                <dl class="info-grid">
                    <div class="info-row"><dt>Mietbeginn:</dt><dd>{self._format_date(mietzeit.get("beginn"))}</dd></div>
                    <div class="info-row"><dt>Befristet:</dt><dd>{"Ja" if mietzeit.get("befristet") else "Nein (unbefristet)"}</dd></div>
                    {f'<div class="info-row"><dt>Mietende:</dt><dd>{self._format_date(mietzeit.get("ende"))}</dd></div>' if mietzeit.get("ende") else ""}
                    {f'<div class="info-row"><dt>Mindestmietzeit:</dt><dd>{mietzeit.get("mindestmietzeit_monate")} Monate</dd></div>' if mietzeit.get("mindestmietzeit_monate") else ""}
                </dl>
            </section>

            <section class="contract-section">
                <h2>§ 5 MIETE UND NEBENKOSTEN</h2>
                <dl class="info-grid">
                    <div class="info-row"><dt>Nettokaltmiete:</dt><dd>{self._format_currency(miete.get("kaltmiete"))}</dd></div>
                    <div class="info-row"><dt>Betriebskosten:</dt><dd>{self._format_currency(miete.get("betriebskosten"))}</dd></div>
                    <div class="info-row"><dt>Heizkosten:</dt><dd>{self._format_currency(miete.get("heizkosten"))}</dd></div>
                </dl>
                <div class="total-box">
                    <span class="total-label">GESAMTMIETE (monatlich):</span>
                    <span class="total-value">{self._format_currency(miete.get("gesamtmiete"))}</span>
                </div>
            </section>

            <section class="contract-section">
                <h2>§ 6 KAUTION</h2>
                <dl class="info-grid">
                    <div class="info-row"><dt>Kautionsbetrag:</dt><dd class="font-bold">{self._format_currency(kaution.get("betrag"))}</dd></div>
                </dl>
                <p class="legal-note">Die Kaution ist gemäß § 551 BGB auf maximal drei Nettokaltmieten begrenzt.</p>
            </section>

            <section class="contract-section">
                <h2>§ 7 BANKVERBINDUNG</h2>
                <dl class="info-grid">
                    <div class="info-row"><dt>Bank:</dt><dd>{bankverbindung.get("bank_name", "-")}</dd></div>
                    <div class="info-row"><dt>IBAN:</dt><dd>{bankverbindung.get("iban", "-")}</dd></div>
                    {f'<div class="info-row"><dt>BIC:</dt><dd>{bankverbindung.get("bic")}</dd></div>' if bankverbindung.get("bic") else ""}
                    {f'<div class="info-row"><dt>Verwendungszweck:</dt><dd>{bankverbindung.get("verwendungszweck")}</dd></div>' if bankverbindung.get("verwendungszweck") else ""}
                </dl>
            </section>
        """

        # Vereinbarungen section if present
        if vereinbarungen and (
            vereinbarungen.get("besonderheiten") or vereinbarungen.get("sonstige")
        ):
            html += f"""
            <section class="contract-section">
                <h2>§ 8 SONSTIGE VEREINBARUNGEN</h2>
                {f"<p>{vereinbarungen.get('besonderheiten')}</p>" if vereinbarungen.get("besonderheiten") else ""}
                {f"<p>{vereinbarungen.get('sonstige')}</p>" if vereinbarungen.get("sonstige") else ""}
            </section>
            """

        # Signature section
        html += """
            <section class="contract-section signature-section">
                <h2>§ 9 UNTERSCHRIFTEN</h2>
                <p class="signature-note">Mit der digitalen Unterschrift bestätigen alle Parteien die Richtigkeit der Angaben und stimmen den Vertragsbedingungen zu.</p>
            </section>
        </div>

        <style>
            .contract-document {
                font-family: 'Georgia', 'Times New Roman', serif;
                max-width: 52rem;
                margin: 0 auto;
                background: white;
                border-radius: 0.75rem;
                box-shadow: 0 4px 24px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04);
                border: 1px solid #e2e8f0;
                padding: 2.5rem 2rem;
                color: #1e293b;
            }
            @media (min-width: 640px) {
                .contract-document { padding: 3rem 3.5rem; }
            }
            .contract-header {
                text-align: center;
                padding-bottom: 1.5rem;
                margin-bottom: 2rem;
                border-bottom: 2px solid #f59e0b;
            }
            .contract-header h1 {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 1rem;
                font-weight: 700;
                letter-spacing: 0.15em;
                color: #1e293b;
                text-transform: uppercase;
                margin: 0 0 0.25rem 0;
            }
            .contract-subtitle {
                font-size: 0.8rem;
                color: #94a3b8;
                font-style: italic;
            }
            .contract-number {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 0.75rem;
                color: #94a3b8;
                margin-top: 0.5rem;
                letter-spacing: 0.05em;
            }
            .contract-section {
                padding: 1.5rem 0;
                border-bottom: 1px solid #f1f5f9;
            }
            .contract-section:last-child {
                border-bottom: none;
                padding-bottom: 0;
            }
            .contract-section h2 {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 0.75rem;
                font-weight: 600;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin: 0 0 1rem 0;
                padding-left: 0.75rem;
                border-left: 3px solid #f59e0b;
            }
            .contract-section h3 {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 0.8rem;
                font-weight: 600;
                color: #475569;
                margin: 1.25rem 0 0.75rem 0;
            }
            .info-grid {
                display: flex;
                flex-direction: column;
                gap: 0.625rem;
            }
            .info-row {
                display: flex;
                flex-wrap: wrap;
                align-items: baseline;
            }
            .info-row dt {
                width: 160px;
                flex-shrink: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 0.75rem;
                font-weight: 500;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }
            .info-row dd {
                flex: 1;
                font-size: 0.9rem;
                font-weight: 400;
                color: #1e293b;
                margin: 0;
            }
            .total-box {
                margin-top: 1.25rem;
                padding: 1rem 1.25rem;
                background: #fffbeb;
                border: 1px solid #fde68a;
                border-radius: 0.5rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .total-label {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 0.8rem;
                font-weight: 600;
                color: #475569;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            .total-value {
                font-size: 1.125rem;
                font-weight: 700;
                color: #b45309;
            }
            .legal-note {
                margin-top: 0.75rem;
                padding: 0.625rem 0.875rem;
                background: #f8fafc;
                border-left: 2px solid #cbd5e1;
                border-radius: 0 0.25rem 0.25rem 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 0.75rem;
                color: #64748b;
                font-style: italic;
            }
            .signature-note {
                font-size: 0.85rem;
                color: #94a3b8;
                font-style: italic;
                line-height: 1.6;
            }
            .font-bold { font-weight: 600; }

            @media (max-width: 640px) {
                .contract-document { padding: 1.5rem 1.25rem; }
                .info-row { flex-direction: column; gap: 0.125rem; }
                .info-row dt { width: 100%; }
                .total-box { flex-direction: column; gap: 0.375rem; text-align: center; }
                .contract-section h2 { font-size: 0.7rem; }
            }
        </style>
        """

        return html
