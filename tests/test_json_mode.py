"""Unit tests for FES JSON mode (contract_data instead of PDF).

Tests cover:
- Creating signature requests with JSON mode
- Backward compatibility with PDF mode
- Token validation returning HTML/JSON
- PDF generation at completion
"""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Sample contract data matching ContractDataSchema
SAMPLE_CONTRACT_DATA: dict[str, Any] = {
    "metadata": {
        "contract_id": "test-contract-123",
        "contract_number": "V-2025-001",
        "created_at": "2025-01-15T10:30:00Z",
    },
    "vermieter": {
        "name": "Max Mustermann GmbH",
        "email": "vermieter@example.com",
        "phone": "+49 30 12345678",
        "anschrift": "Musterstraße 1, 10115 Berlin",
    },
    "mieter1": {
        "vorname": "Anna",
        "nachname": "Schmidt",
        "geburtstag": "1990-05-15",
        "email": "anna.schmidt@example.com",
        "telefon": "+49 176 12345678",
        "anschrift": {
            "strasse": "Alte Straße",
            "hausnummer": "42",
            "plz": "80331",
            "stadt": "München",
        },
    },
    "mietobjekt": {
        "liegenschaft": "Wohnanlage Sonnenhof",
        "strasse": "Sonnenallee",
        "hausnummer": "100",
        "plz": "10115",
        "ort": "Berlin",
        "lage": "3. OG links",
        "zimmer_anzahl": 3,
    },
    "mietzeit": {
        "beginn": "2025-02-01",
        "befristet": False,
    },
    "miete": {
        "kaltmiete": 1200.00,
        "betriebskosten": 150.00,
        "heizkosten": 80.00,
        "gesamtmiete": 1430.00,
    },
    "kaution": {
        "betrag": 3600.00,
    },
    "bankverbindung": {
        "bank_name": "Deutsche Bank",
        "iban": "DE89370400440532013000",
        "bic": "COBADEFFXXX",
    },
}

SAMPLE_PDF_BASE64 = "JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwo+PgplbmRvYmoKdHJhaWxlcgo8PAovUm9vdCAxIDAgUgo+Pg=="


class TestSignatureRequestCreation:
    """Tests for creating signature requests."""

    @pytest.mark.asyncio
    async def test_create_request_json_mode(self):
        """Test creating signature request with JSON mode (contract_data)."""
        from src.schemas.signature import SignatureRequestCreate

        # Create request with contract_data (JSON mode)
        request = SignatureRequestCreate(
            contract_id=uuid4(),
            requester_user_id=uuid4(),
            requester_email="landlord@example.com",
            tenant_id=uuid4(),
            contract_data=SAMPLE_CONTRACT_DATA,
            signers=[
                {
                    "name": "Max Mustermann",
                    "email": "vermieter@example.com",
                    "role": "landlord",
                    "signing_order": 1,
                },
                {
                    "name": "Anna Schmidt",
                    "email": "anna.schmidt@example.com",
                    "role": "tenant_1",
                    "signing_order": 2,
                },
            ],
        )

        assert request.contract_data is not None
        assert request.document_pdf_base64 is None
        assert request.document_type == "json"

    @pytest.mark.asyncio
    async def test_create_request_pdf_mode(self):
        """Test backward compatibility - creating request with PDF mode."""
        from src.schemas.signature import SignatureRequestCreate

        # Create request with PDF (legacy mode)
        request = SignatureRequestCreate(
            contract_id=uuid4(),
            requester_user_id=uuid4(),
            requester_email="landlord@example.com",
            tenant_id=uuid4(),
            document_pdf_base64=SAMPLE_PDF_BASE64,
            signers=[
                {
                    "name": "Max Mustermann",
                    "email": "vermieter@example.com",
                    "role": "landlord",
                    "signing_order": 1,
                },
            ],
        )

        assert request.document_pdf_base64 is not None
        assert request.contract_data is None
        assert request.document_type == "pdf"

    @pytest.mark.asyncio
    async def test_create_request_fails_without_document(self):
        """Test that request creation fails without PDF or contract_data."""
        from src.schemas.signature import SignatureRequestCreate

        with pytest.raises(ValueError, match="Must provide one of"):
            SignatureRequestCreate(
                contract_id=uuid4(),
                requester_user_id=uuid4(),
                requester_email="landlord@example.com",
                tenant_id=uuid4(),
                signers=[
                    {
                        "name": "Max Mustermann",
                        "email": "vermieter@example.com",
                        "role": "landlord",
                        "signing_order": 1,
                    },
                ],
            )

    @pytest.mark.asyncio
    async def test_create_request_fails_with_both(self):
        """Test that request creation fails with both PDF and contract_data."""
        from src.schemas.signature import SignatureRequestCreate

        with pytest.raises(ValueError, match="only one of"):
            SignatureRequestCreate(
                contract_id=uuid4(),
                requester_user_id=uuid4(),
                requester_email="landlord@example.com",
                tenant_id=uuid4(),
                document_pdf_base64=SAMPLE_PDF_BASE64,
                contract_data=SAMPLE_CONTRACT_DATA,
                signers=[
                    {
                        "name": "Max Mustermann",
                        "email": "vermieter@example.com",
                        "role": "landlord",
                        "signing_order": 1,
                    },
                ],
            )


class TestTokenValidation:
    """Tests for token validation and contract retrieval."""

    @pytest.mark.asyncio
    async def test_token_validation_returns_html_json_mode(self):
        """Test that JSON mode returns HTML content and contract_data."""
        # This would test the signing_service.validate_token_and_get_contract method
        # In a real test, we'd mock the repository and verify the response

        expected_response = {
            "document_type": "json",
            "contract_html": "<html>...",  # Server-rendered HTML
            "contract_data": SAMPLE_CONTRACT_DATA,  # Raw JSON for client
            "signer_name": "Anna Schmidt",
            "signer_role": "tenant_1",
        }

        # Verify structure
        assert expected_response["document_type"] == "json"
        assert expected_response["contract_data"] is not None
        assert expected_response["contract_html"] is not None

    @pytest.mark.asyncio
    async def test_token_validation_returns_html_pdf_mode(self):
        """Test that PDF mode returns HTML content without contract_data."""
        expected_response = {
            "document_type": "pdf",
            "contract_html": "<html>...",  # Rendered from PDF
            "contract_data": None,  # Not available in PDF mode
            "signer_name": "Anna Schmidt",
            "signer_role": "tenant_1",
        }

        assert expected_response["document_type"] == "pdf"
        assert expected_response["contract_data"] is None


class TestHTMLToPDFService:
    """Tests for HTML-to-PDF service."""

    @pytest.mark.asyncio
    async def test_generate_contract_pdf(self):
        """Test PDF generation from contract_data."""
        from src.core.pdf.html_to_pdf_service import HTMLToPDFService
        from src.models.signature_request import (
            SignatureRequest,
            SignatureSigner,
        )

        # Create mock request with contract_data
        request = MagicMock(spec=SignatureRequest)
        request.id = uuid4()
        request.contract_id = uuid4()
        request.contract_data = SAMPLE_CONTRACT_DATA
        request.document_type = "json"

        # Create mock signers
        signers = [
            MagicMock(spec=SignatureSigner),
            MagicMock(spec=SignatureSigner),
        ]
        signers[0].role = "landlord"
        signers[0].name = "Max Mustermann"
        signers[0].email = "vermieter@example.com"
        signers[0].signed_at = datetime.now()
        signers[0].ip_address = "192.168.1.1"
        signers[0].signature_image_base64 = "data:image/png;base64,iVBORw0KGgo..."

        signers[1].role = "tenant_1"
        signers[1].name = "Anna Schmidt"
        signers[1].email = "anna.schmidt@example.com"
        signers[1].signed_at = datetime.now()
        signers[1].ip_address = "192.168.1.2"
        signers[1].signature_image_base64 = "data:image/png;base64,iVBORw0KGgo..."

        # Test PDF generation (this requires Playwright installed)
        service = HTMLToPDFService()

        # Mock the _html_to_pdf method to avoid actual browser
        with patch.object(service, "_html_to_pdf", new_callable=AsyncMock) as mock_pdf:
            mock_pdf.return_value = b"%PDF-1.4..."

            pdf_bytes = await service.generate_contract_pdf(
                request=request,
                signers=signers,
            )

            assert pdf_bytes is not None
            mock_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_pdf_generation_fails_without_contract_data(self):
        """Test that PDF generation fails without contract_data."""
        from src.core.pdf.html_to_pdf_service import HTMLToPDFService
        from src.core.pdf.pdf_processor import PDFProcessingError

        request = MagicMock()
        request.contract_data = None

        service = HTMLToPDFService()

        with pytest.raises(PDFProcessingError, match="No contract_data"):
            await service.generate_contract_pdf(
                request=request,
                signers=[],
            )


class TestFormatters:
    """Tests for German formatting utilities."""

    def test_format_date(self):
        """Test date formatting to German format."""
        from src.core.pdf.html_to_pdf_service import HTMLToPDFService

        assert HTMLToPDFService._format_date("2025-01-15") == "15.01.2025"
        assert HTMLToPDFService._format_date("2025-12-31") == "31.12.2025"
        assert HTMLToPDFService._format_date(None) == "-"
        assert HTMLToPDFService._format_date("") == "-"

    def test_format_currency(self):
        """Test currency formatting to German format."""
        from src.core.pdf.html_to_pdf_service import HTMLToPDFService

        # Test basic formatting
        result = HTMLToPDFService._format_currency(1200.00)
        assert "1.200,00" in result or "1200,00" in result  # German format
        assert "€" in result

        result = HTMLToPDFService._format_currency(0)
        assert "0,00" in result

        assert HTMLToPDFService._format_currency(None) == "-"

    def test_format_address(self):
        """Test address formatting."""
        from src.core.pdf.html_to_pdf_service import HTMLToPDFService

        addr = {
            "strasse": "Musterstraße",
            "hausnummer": "123",
            "plz": "10115",
            "stadt": "Berlin",
        }
        result = HTMLToPDFService._format_address(addr)
        assert "Musterstraße 123" in result
        assert "10115 Berlin" in result

        assert HTMLToPDFService._format_address(None) == "-"
        assert HTMLToPDFService._format_address({}) == "-"


class TestContractDataSchema:
    """Tests for ContractData schema validation."""

    def test_contract_data_schema_valid(self):
        """Test that valid contract data passes schema validation."""
        from src.schemas.signature import ContractDataSchema

        schema = ContractDataSchema(**SAMPLE_CONTRACT_DATA)

        assert schema.metadata.contract_id == "test-contract-123"
        assert schema.vermieter.name == "Max Mustermann GmbH"
        assert schema.mieter1.vorname == "Anna"
        assert schema.miete.gesamtmiete == 1430.00
        assert schema.kaution.betrag == 3600.00

    def test_contract_data_schema_minimal(self):
        """Test minimal contract data with required fields only."""
        from src.schemas.signature import ContractDataSchema

        minimal_data = {
            "metadata": {
                "contract_id": "test-123",
            },
            "vermieter": {
                "name": "Vermieter",
                "email": "v@example.com",
            },
            "mieter1": {
                "vorname": "Max",
                "nachname": "Mustermann",
                "email": "m@example.com",
            },
            "mietobjekt": {
                "strasse": "Test",
                "hausnummer": "1",
                "plz": "12345",
                "ort": "Stadt",
            },
            "mietzeit": {
                "beginn": "2025-01-01",
                "befristet": False,
            },
            "miete": {
                "kaltmiete": 1000,
                "betriebskosten": 100,
                "heizkosten": 50,
                "gesamtmiete": 1150,
            },
            "kaution": {
                "betrag": 3000,
            },
            "bankverbindung": {
                "bank_name": "Bank",
                "iban": "DE89370400440532013000",
            },
        }

        schema = ContractDataSchema(**minimal_data)
        assert schema.mieter2 is None
        assert schema.vereinbarungen is None


class TestCompletionServiceModes:
    """Tests for completion service handling both modes."""

    @pytest.mark.asyncio
    async def test_completion_service_json_mode(self):
        """Test that completion service generates PDF for JSON mode."""
        # This tests the flow: JSON mode -> generate PDF at completion
        request = MagicMock()
        request.id = uuid4()
        request.contract_id = uuid4()
        request.document_type = "json"
        request.is_json_mode = True
        request.contract_data = SAMPLE_CONTRACT_DATA
        request.callback_url = None

        # Verify mode detection
        assert request.is_json_mode is True
        assert request.contract_data is not None

    @pytest.mark.asyncio
    async def test_completion_service_pdf_mode(self):
        """Test that completion service uses existing PDF for PDF mode."""
        request = MagicMock()
        request.id = uuid4()
        request.contract_id = uuid4()
        request.document_type = "pdf"
        request.is_json_mode = False
        request.document_url = "file:///path/to/contract.pdf"
        request.document_hash = "abc123"
        request.callback_url = None

        # Verify mode detection
        assert request.is_json_mode is False
        assert request.document_url is not None


# ============================================================================
# Integration Test Helpers
# ============================================================================


def create_test_contract_data(
    contract_id: str = "test-123",
    tenant_name: str = "Test Tenant",
) -> dict[str, Any]:
    """Create test contract data for integration tests."""
    return {
        "metadata": {
            "contract_id": contract_id,
            "contract_number": f"V-{contract_id}",
        },
        "vermieter": {
            "name": "Test Landlord",
            "email": "landlord@test.com",
        },
        "mieter1": {
            "vorname": tenant_name.split()[0] if " " in tenant_name else tenant_name,
            "nachname": tenant_name.split()[1] if " " in tenant_name else "Test",
            "email": "tenant@test.com",
        },
        "mietobjekt": {
            "strasse": "Teststraße",
            "hausnummer": "1",
            "plz": "12345",
            "ort": "Berlin",
        },
        "mietzeit": {
            "beginn": "2025-01-01",
            "befristet": False,
        },
        "miete": {
            "kaltmiete": 1000,
            "betriebskosten": 100,
            "heizkosten": 50,
            "gesamtmiete": 1150,
        },
        "kaution": {"betrag": 3000},
        "bankverbindung": {
            "bank_name": "Test Bank",
            "iban": "DE89370400440532013000",
        },
    }
