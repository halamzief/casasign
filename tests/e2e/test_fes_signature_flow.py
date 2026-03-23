"""
E2E tests for the complete FES signature flow.

Tests the full lifecycle:
1. Health check
2. Create signature request (JSON mode, 2 signers)
3. Validate token for signer 1 (landlord)
4. Complete signature for signer 1
5. Check status (in_progress)
6. Validate token for signer 2 (tenant)
7. Complete signature for signer 2
8. Check status (completed)
9. Process completed request (PDF generation)
10. Download signed PDF

Requires: FES service running on FES_API_URL (default: http://localhost:9101)
"""

import os
import uuid
from datetime import UTC, datetime
from typing import Generator

import httpx
import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FES_API_URL = os.getenv("FES_API_URL", "https://sign.signcasa.de")
REQUEST_TIMEOUT = 30.0

# Minimal 1x1 transparent PNG for signature image
DUMMY_SIGNATURE_BASE64 = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_client() -> Generator[httpx.Client, None, None]:
    """Synchronous httpx client for FES API."""
    with httpx.Client(base_url=FES_API_URL, timeout=REQUEST_TIMEOUT) as client:
        yield client


@pytest.fixture(scope="module")
def contract_ids() -> dict[str, str]:
    """Generate unique IDs for this test run."""
    return {
        "contract_id": str(uuid.uuid4()),
        "requester_user_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
    }


@pytest.fixture(scope="module")
def sample_contract_data(contract_ids: dict[str, str]) -> dict:
    """Sample German rental contract data (JSON mode)."""
    return {
        "metadata": {
            "contract_id": contract_ids["contract_id"],
            "contract_number": "V-E2E-TEST-001",
            "created_at": datetime.now(UTC).isoformat(),
        },
        "vermieter": {
            "name": "Max Mustermann",
            "email": "vermieter-e2e@test.signcasa.de",
            "phone": "+4917612345678",
            "anschrift": "Musterstraße 1, 10115 Berlin",
        },
        "mieter1": {
            "vorname": "Anna",
            "nachname": "Schmidt",
            "geburtstag": "1990-05-15",
            "email": "mieter-e2e@test.signcasa.de",
            "telefon": "+4917687654321",
            "anschrift": None,
        },
        "mietobjekt": {
            "strasse": "Berliner Straße",
            "hausnummer": "42",
            "plz": "10115",
            "ort": "Berlin",
            "lage": "3. OG links",
            "zimmer_anzahl": 3,
            "personenanzahl": 2,
        },
        "mietzeit": {
            "beginn": "2026-04-01",
            "befristet": False,
        },
        "miete": {
            "kaltmiete": 850.00,
            "betriebskosten": 150.00,
            "heizkosten": 80.00,
            "gesamtmiete": 1080.00,
        },
        "kaution": {
            "betrag": 2550.00,
        },
        "bankverbindung": {
            "bank_name": "Deutsche Bank",
            "iban": "DE89370400440532013000",
            "bic": "DEUTDEDB",
            "verwendungszweck": "Miete V-E2E-TEST-001",
        },
    }


def _build_signature_request_payload(
    contract_ids: dict[str, str],
    contract_data: dict,
) -> dict:
    """Build the POST /api/sign/request payload."""
    return {
        "contract_id": contract_ids["contract_id"],
        "requester_user_id": contract_ids["requester_user_id"],
        "requester_email": "vermieter-e2e@test.signcasa.de",
        "tenant_id": contract_ids["tenant_id"],
        "contract_data": contract_data,
        "signers": [
            {
                "name": "Max Mustermann",
                "email": "vermieter-e2e@test.signcasa.de",
                "role": "landlord",
                "signing_order": 1,
                "verification_method": "email_link",
            },
            {
                "name": "Anna Schmidt",
                "email": "mieter-e2e@test.signcasa.de",
                "role": "tenant_1",
                "signing_order": 2,
                "verification_method": "email_link",
            },
        ],
        "callback_url": None,
        "expires_in_days": 7,
    }


# ---------------------------------------------------------------------------
# Shared state across ordered tests
# ---------------------------------------------------------------------------


class FlowState:
    """Shared state for the sequential signature flow tests."""

    request_id: str = ""
    signer_tokens: dict[str, str] = {}  # email -> token
    signer_ids: dict[str, str] = {}  # email -> signer_id


_state = FlowState()


# ---------------------------------------------------------------------------
# Tests (ordered — run with pytest-ordering or natural order)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestFESHealthCheck:
    """Verify FES service is reachable before running flow tests."""

    def test_health_endpoint(self, api_client: httpx.Client) -> None:
        """FES /health returns healthy status."""
        resp = api_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.e2e
class TestFESSignatureFlowE2E:
    """Complete sequential signature flow — tests must run in order."""

    # -- Step 1: Create signature request (JSON mode) -----------------------

    def test_01_create_signature_request(
        self,
        api_client: httpx.Client,
        contract_ids: dict[str, str],
        sample_contract_data: dict,
    ) -> None:
        """POST /api/sign/request creates a new signature request."""
        payload = _build_signature_request_payload(contract_ids, sample_contract_data)

        resp = api_client.post("/api/sign/request", json=payload)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

        data = resp.json()

        # Verify response structure
        assert "id" in data
        assert data["status"] == "pending"
        assert data["document_type"] == "json"
        assert data["contract_id"] == contract_ids["contract_id"]
        assert len(data["signers"]) == 2

        # Store request ID and signer tokens
        _state.request_id = str(data["id"])

        for signer in data["signers"]:
            email = signer["email"]
            _state.signer_ids[email] = str(signer["id"])
            if signer.get("signing_link"):
                # Extract token from signing link URL
                token = signer["signing_link"].rsplit("/", 1)[-1]
                _state.signer_tokens[email] = token

    # -- Step 2: Check initial status (pending) -----------------------------

    def test_02_initial_status_is_pending(self, api_client: httpx.Client) -> None:
        """GET /api/sign/status/{request_id} returns pending."""
        assert _state.request_id, "No request_id — test_01 must run first"

        resp = api_client.get(f"/api/sign/status/{_state.request_id}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "pending"
        assert data["total_signers"] == 2
        assert data["signed_count"] == 0

    # -- Step 3: Validate token for signer 1 (landlord) --------------------

    def test_03_validate_landlord_token(self, api_client: httpx.Client) -> None:
        """GET /api/sign/{token} validates landlord's signing link."""
        landlord_email = "vermieter-e2e@test.signcasa.de"
        token = _state.signer_tokens.get(landlord_email)
        assert token, f"No token for {landlord_email}"

        resp = api_client.get(f"/api/sign/{token}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["signer_email"] == landlord_email
        assert data["signer_role"] == "landlord"
        assert data["document_type"] == "json"
        assert data["is_already_signed"] is False
        assert data["contract_html"]  # Non-empty rendered HTML

    # -- Step 4: Complete signature for signer 1 (landlord) -----------------

    def test_04_complete_landlord_signature(self, api_client: httpx.Client) -> None:
        """POST /api/sign/{token}/complete — landlord signs."""
        landlord_email = "vermieter-e2e@test.signcasa.de"
        token = _state.signer_tokens.get(landlord_email)
        assert token, f"No token for {landlord_email}"

        submission = {
            "signature_image_base64": DUMMY_SIGNATURE_BASE64,
            "consents": {
                "identity_confirmed": True,
                "contract_reviewed": True,
            },
        }

        resp = api_client.post(f"/api/sign/{token}/complete", json=submission)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        data = resp.json()
        assert data["success"] is True
        assert data["all_completed"] is False  # Tenant hasn't signed yet
        assert data["next_signer_name"] == "Anna Schmidt"

    # -- Step 5: Status should be in_progress after first signer ------------

    def test_05_status_in_progress(self, api_client: httpx.Client) -> None:
        """After landlord signs, status should be in_progress."""
        resp = api_client.get(f"/api/sign/status/{_state.request_id}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["signed_count"] == 1
        assert len(data["pending_signers"]) == 1

    # -- Step 6: Validate token for signer 2 (tenant) ----------------------

    def test_06_validate_tenant_token(self, api_client: httpx.Client) -> None:
        """GET /api/sign/{token} validates tenant's signing link."""
        tenant_email = "mieter-e2e@test.signcasa.de"
        token = _state.signer_tokens.get(tenant_email)
        assert token, f"No token for {tenant_email}"

        resp = api_client.get(f"/api/sign/{token}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["signer_email"] == tenant_email
        assert data["signer_role"] == "tenant_1"
        assert data["is_already_signed"] is False

    # -- Step 7: Complete signature for signer 2 (tenant) -------------------

    def test_07_complete_tenant_signature(self, api_client: httpx.Client) -> None:
        """POST /api/sign/{token}/complete — tenant signs."""
        tenant_email = "mieter-e2e@test.signcasa.de"
        token = _state.signer_tokens.get(tenant_email)
        assert token, f"No token for {tenant_email}"

        submission = {
            "signature_image_base64": DUMMY_SIGNATURE_BASE64,
            "consents": {
                "identity_confirmed": True,
                "contract_reviewed": True,
                "deposit_insurance_consent": True,
            },
        }

        resp = api_client.post(f"/api/sign/{token}/complete", json=submission)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        data = resp.json()
        assert data["success"] is True
        assert data["all_completed"] is True

    # -- Step 8: Status should be completed ---------------------------------

    def test_08_status_completed(self, api_client: httpx.Client) -> None:
        """After both sign, status should be completed."""
        resp = api_client.get(f"/api/sign/status/{_state.request_id}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "completed"
        assert data["signed_count"] == 2
        assert data["completed_at"] is not None

    # -- Step 9: Process completed request (PDF generation) -----------------

    def test_09_process_completed(self, api_client: httpx.Client) -> None:
        """POST /api/sign/process-completed/{id} generates signed PDF."""
        resp = api_client.post(f"/api/sign/process-completed/{_state.request_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    # -- Step 10: Download signed PDF ---------------------------------------

    def test_10_download_signed_pdf_info(self, api_client: httpx.Client) -> None:
        """GET /api/sign/download/{id} returns PDF metadata."""
        resp = api_client.get(f"/api/sign/download/{_state.request_id}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["success"] is True
        assert data["signer_count"] == 2
        assert data["file_size"] > 0

    def test_11_download_signed_pdf_file(self, api_client: httpx.Client) -> None:
        """GET /api/sign/download/{id}/file returns actual PDF bytes."""
        resp = api_client.get(f"/api/sign/download/{_state.request_id}/file")
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/pdf"
        assert len(resp.content) > 100  # Non-trivial PDF


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestFESEdgeCases:
    """Edge case and error handling tests."""

    def test_invalid_token_returns_400(self, api_client: httpx.Client) -> None:
        """GET /api/sign/{invalid_token} returns 400."""
        resp = api_client.get("/api/sign/invalid-token-that-does-not-exist-at-all-x")
        assert resp.status_code in (400, 404)

    def test_create_request_missing_signers_returns_422(
        self, api_client: httpx.Client
    ) -> None:
        """POST /api/sign/request without signers returns 422."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "requester_user_id": str(uuid.uuid4()),
            "requester_email": "test@test.de",
            "tenant_id": str(uuid.uuid4()),
            "contract_data": {
                "metadata": {"contract_id": "test"},
                "vermieter": {"name": "Test"},
                "mieter1": {"vorname": "A", "nachname": "B"},
                "mietobjekt": {"strasse": "S", "hausnummer": "1", "plz": "10115", "ort": "Berlin"},
                "mietzeit": {"beginn": "2026-04-01", "befristet": False},
                "miete": {"kaltmiete": 500, "betriebskosten": 100, "heizkosten": 50, "gesamtmiete": 650},
                "kaution": {"betrag": 1500},
                "bankverbindung": {"bank_name": "Test", "iban": "DE00000000000000000000"},
            },
            "signers": [],  # Empty — should fail validation
        }
        resp = api_client.post("/api/sign/request", json=payload)
        assert resp.status_code == 422

    def test_create_request_no_document_returns_422(
        self, api_client: httpx.Client
    ) -> None:
        """POST /api/sign/request without document or contract_data returns 422."""
        payload = {
            "contract_id": str(uuid.uuid4()),
            "requester_user_id": str(uuid.uuid4()),
            "requester_email": "test@test.de",
            "tenant_id": str(uuid.uuid4()),
            "signers": [
                {
                    "name": "Test",
                    "email": "test@test.de",
                    "role": "landlord",
                    "signing_order": 1,
                    "verification_method": "email_link",
                }
            ],
        }
        resp = api_client.post("/api/sign/request", json=payload)
        assert resp.status_code == 422

    def test_nonexistent_request_status_returns_404(
        self, api_client: httpx.Client
    ) -> None:
        """GET /api/sign/status/{nonexistent_id} returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_client.get(f"/api/sign/status/{fake_id}")
        assert resp.status_code in (404, 500)

    def test_double_sign_returns_error(self, api_client: httpx.Client) -> None:
        """Signing with an already-used token should fail."""
        landlord_email = "vermieter-e2e@test.signcasa.de"
        token = _state.signer_tokens.get(landlord_email)
        if not token:
            pytest.skip("No token available — main flow tests did not run")

        submission = {
            "signature_image_base64": DUMMY_SIGNATURE_BASE64,
            "consents": {
                "identity_confirmed": True,
                "contract_reviewed": True,
            },
        }
        resp = api_client.post(f"/api/sign/{token}/complete", json=submission)
        # Should be rejected — already signed
        assert resp.status_code in (400, 409)
