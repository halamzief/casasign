"""FES Pages Router - Serves Jinja2 templates for signing flow."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database.session import get_db_session

router = APIRouter(tags=["pages"])


@router.get("/sign/{token}", response_class=HTMLResponse)
async def signing_page(request: Request, token: str) -> HTMLResponse:
    """Render the signing page for a given token.

    The actual contract data is loaded via API call from the frontend.
    """
    templates = request.app.state.templates
    return await templates.TemplateResponse(
        "sign/signing_page.html",
        {
            "request": request,
            "token": token,
            "signer_name": "",  # Will be loaded via API
            "property_address": "",  # Will be loaded via API
            "kaution_betrag": None,  # Will be loaded via API
        },
    )


@router.get("/sign/{token}/success", response_class=HTMLResponse)
async def success_page(
    request: Request,
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    """Render the success page after signing.

    Fetches contract data to display personalized success content.
    """
    from src.core.repositories.signature_repository import SignatureRepository

    repo = SignatureRepository(session)
    templates = request.app.state.templates

    # Try to get signer data for personalization
    tenant_name = ""
    property_address = ""
    move_in_date = ""
    consents = {}

    try:
        # Get signer by token
        signer = await repo.get_signer_by_token(token)
        if signer:
            tenant_name = signer.get("name", "")
            # Get request data for property info
            request_id = signer.get("signature_request_id")
            if request_id:
                sig_request = await repo.get_request_by_id(request_id)
                if sig_request:
                    property_address = sig_request.get("property_address", "")
                    move_in_date = sig_request.get("move_in_date", "")
                    # Get consents from signer metadata
                    consents = signer.get("consents", {})
    except Exception:
        # Silently fail - show generic success page
        pass

    return await templates.TemplateResponse(
        "sign/success_page.html",
        {
            "request": request,
            "token": token,
            "tenant_name": tenant_name,
            "property_address": property_address,
            "move_in_date": move_in_date,
            "consents": consents,
        },
    )


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request) -> HTMLResponse:
    """Render the home page."""
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>SignCasa Signatures</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50 min-h-screen flex items-center justify-center">
            <div class="text-center">
                <h1 class="text-4xl font-bold text-gray-900 mb-4">SignCasa Signatures</h1>
                <p class="text-gray-600 mb-8">FES-compliant digital signature service</p>
                <div class="space-x-4">
                    <a href="/docs" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                        API Documentation
                    </a>
                    <a href="/health" class="px-6 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300">
                        Health Check
                    </a>
                </div>
                <p class="mt-8 text-sm text-gray-500">Version {settings.service_name} v0.1.0</p>
            </div>
        </body>
        </html>
        """,
        status_code=200,
    )
