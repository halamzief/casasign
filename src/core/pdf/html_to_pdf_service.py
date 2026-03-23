"""HTML-to-PDF Service using Playwright.

Generates high-quality PDFs from HTML templates with Playwright for JSON mode contracts.
Produces A4-formatted PDFs identical to browser print output.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from src.models.signature_request import SignatureRequest, SignatureSigner
from .pdf_processor import PDFProcessingError


class HTMLToPDFService:
    """Service for converting HTML templates to PDF using Playwright."""

    def __init__(self, templates_path: Optional[Path] = None):
        """Initialize HTML-to-PDF service.

        Args:
            templates_path: Path to Jinja2 templates directory.
                           Defaults to src/templates.
        """
        if templates_path is None:
            templates_path = Path(__file__).parent.parent.parent / "templates"

        self.templates_path = templates_path
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=True,
        )

        # Register custom Jinja2 filters
        self.jinja_env.filters["format_date"] = self._format_date
        self.jinja_env.filters["format_datetime"] = self._format_datetime
        self.jinja_env.filters["format_currency"] = self._format_currency
        self.jinja_env.filters["format_address"] = self._format_address
        self.jinja_env.globals["format_date"] = self._format_date
        self.jinja_env.globals["format_datetime"] = self._format_datetime
        self.jinja_env.globals["format_currency"] = self._format_currency
        self.jinja_env.globals["format_address"] = self._format_address

        logger.info(f"HTMLToPDFService initialized with templates from: {templates_path}")

    async def generate_contract_pdf(
        self,
        request: SignatureRequest,
        signers: list[SignatureSigner],
        signature_images: Optional[dict[str, str]] = None,
    ) -> bytes:
        """Generate PDF from contract JSON data with signatures.

        Args:
            request: Signature request with contract_data
            signers: List of signers with signature information
            signature_images: Dict mapping signer role to base64 signature image

        Returns:
            PDF as bytes

        Raises:
            PDFProcessingError: If PDF generation fails
        """
        if not request.contract_data:
            raise PDFProcessingError("No contract_data available for PDF generation")

        logger.info(
            "Generating contract PDF from JSON",
            extra={
                "request_id": str(request.id),
                "contract_id": str(request.contract_id),
                "signer_count": len(signers),
            },
        )

        try:
            # Build signature images dict from signers if not provided
            if signature_images is None:
                signature_images = {}
                for signer in signers:
                    if signer.signature_image_base64:
                        # Extract base64 data without data URI prefix
                        sig_data = signer.signature_image_base64
                        if sig_data.startswith("data:"):
                            sig_data = sig_data.split(",", 1)[1]
                        signature_images[signer.role] = sig_data

            # Prepare template context
            context = self._prepare_template_context(
                request=request,
                signers=signers,
                signature_images=signature_images,
            )

            # Render HTML from template
            html_content = self._render_template("contract_final.html", context)

            # Convert HTML to PDF using Playwright
            pdf_bytes = await self._html_to_pdf(html_content)

            logger.success(
                "Contract PDF generated successfully",
                extra={
                    "request_id": str(request.id),
                    "pdf_size": len(pdf_bytes),
                },
            )

            return pdf_bytes

        except Exception as e:
            logger.error(f"Failed to generate contract PDF: {e}", exc_info=True)
            raise PDFProcessingError(f"PDF generation failed: {e}") from e

    def _prepare_template_context(
        self,
        request: SignatureRequest,
        signers: list[SignatureSigner],
        signature_images: dict[str, str],
    ) -> dict:
        """Prepare context dictionary for Jinja2 template.

        Args:
            request: Signature request
            signers: List of signers
            signature_images: Dict mapping role to base64 signature

        Returns:
            Context dictionary for template rendering
        """
        contract = request.contract_data or {}

        # Build signer data for template
        signer_data = []
        for signer in signers:
            signer_data.append(
                {
                    "role": signer.role,
                    "name": signer.name,
                    "email": signer.email,
                    "signed_at": signer.signed_at,
                    "ip_address": str(signer.ip_address) if signer.ip_address else None,
                }
            )

        return {
            "contract": contract,
            "request": {
                "id": str(request.id),
                "contract_id": str(request.contract_id),
            },
            "signers": signer_data,
            "signature_images": signature_images,
            "generation_date": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC"),
        }

    def _render_template(self, template_name: str, context: dict) -> str:
        """Render Jinja2 template with context.

        Args:
            template_name: Name of template file
            context: Template context

        Returns:
            Rendered HTML string
        """
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)

    async def _html_to_pdf(self, html_content: str) -> bytes:
        """Convert HTML to PDF using Playwright.

        Args:
            html_content: Complete HTML document

        Returns:
            PDF as bytes
        """
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            # Launch headless Chromium
            browser = await p.chromium.launch(headless=True)

            try:
                page = await browser.new_page()

                # Set content and wait for full render
                await page.set_content(html_content, wait_until="networkidle")

                # Generate PDF with A4 format
                pdf_bytes = await page.pdf(
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "15mm",
                        "bottom": "15mm",
                        "left": "20mm",
                        "right": "20mm",
                    },
                )

                return pdf_bytes

            finally:
                await browser.close()

    # --- Jinja2 filter functions ---

    @staticmethod
    def _format_date(date_str: Optional[str]) -> str:
        """Format date string to German format DD.MM.YYYY.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Formatted date string
        """
        if not date_str:
            return "-"

        try:
            if isinstance(date_str, datetime):
                return date_str.strftime("%d.%m.%Y")

            parts = str(date_str).split("-")
            if len(parts) == 3:
                year, month, day = parts
                return f"{day}.{month}.{year}"
            return str(date_str)
        except Exception:
            return str(date_str) if date_str else "-"

    @staticmethod
    def _format_datetime(dt: Optional[datetime]) -> str:
        """Format datetime to German format DD.MM.YYYY HH:MM.

        Args:
            dt: Datetime object

        Returns:
            Formatted datetime string
        """
        if not dt:
            return "-"

        try:
            if isinstance(dt, datetime):
                return dt.strftime("%d.%m.%Y %H:%M")
            return str(dt)
        except Exception:
            return str(dt) if dt else "-"

    @staticmethod
    def _format_currency(amount: Optional[float]) -> str:
        """Format amount as German currency (EUR).

        Args:
            amount: Amount in EUR

        Returns:
            Formatted currency string (e.g., "1.200,00 EUR")
        """
        if amount is None:
            return "-"

        try:
            # Format with German locale style
            formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{formatted} €"
        except Exception:
            return f"{amount} €" if amount else "-"

    @staticmethod
    def _format_address(addr: Optional[dict]) -> str:
        """Format address object to single line.

        Args:
            addr: Address dictionary with strasse, hausnummer, plz, stadt/ort

        Returns:
            Formatted address string
        """
        if not addr:
            return "-"

        try:
            strasse = addr.get("strasse", "")
            hausnummer = addr.get("hausnummer", "")
            plz = addr.get("plz", "")
            stadt = addr.get("stadt") or addr.get("ort", "")

            street_part = f"{strasse} {hausnummer}".strip()
            city_part = f"{plz} {stadt}".strip()

            if street_part and city_part:
                return f"{street_part}, {city_part}"
            return street_part or city_part or "-"
        except Exception:
            return "-"
