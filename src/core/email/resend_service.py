"""Resend email service integration."""

import asyncio
from typing import Any, Optional

import resend
from loguru import logger
from pydantic import EmailStr

from src.config import settings
from src.core.email.template_service import EmailTemplateService
from src.schemas.email import EmailSendResponse


class ResendEmailService:
    """Service for sending emails via Resend."""

    def __init__(self, template_service: EmailTemplateService):
        """Initialize Resend service."""
        self.template_service = template_service
        resend.api_key = settings.resend_api_key

    async def send_email(
        self,
        to_email: EmailStr,
        to_name: str,
        template_key: str,
        variables: dict[str, Any],
        language: str = "de",
        tenant_id: Optional[str] = None,
    ) -> EmailSendResponse:
        """Send email using template.

        Args:
            to_email: Recipient email address
            to_name: Recipient name
            template_key: Email template key
            variables: Template variables
            language: Email language
            tenant_id: Optional tenant ID for custom templates

        Returns:
            EmailSendResponse with send status
        """
        logger.info(
            "Sending email",
            to_email=to_email,
            template_key=template_key,
            tenant_id=tenant_id,
        )

        try:
            # Render template
            rendered = await self.template_service.render_template(
                template_key=template_key,
                variables=variables,
                language=language,
                tenant_id=tenant_id,
            )

            # Send via Resend
            params: resend.Emails.SendParams = {
                "from": f"{settings.from_name} <{settings.from_email}>",
                "to": [to_email],
                "subject": rendered.subject,
                "html": rendered.body_html,
                "text": rendered.body_text,
            }

            loop = asyncio.get_event_loop()
            email = await loop.run_in_executor(None, lambda: resend.Emails.send(params))

            logger.success(
                "Email sent successfully",
                to_email=to_email,
                email_id=email.get("id"),
                template_key=template_key,
            )

            return EmailSendResponse(
                success=True,
                message="Email sent successfully",
                email_id=email.get("id"),
            )

        except Exception as e:
            logger.error(
                "Failed to send email",
                to_email=to_email,
                template_key=template_key,
                error=str(e),
            )
            return EmailSendResponse(
                success=False,
                message=f"Failed to send email: {str(e)}",
                email_id=None,
            )

    async def send_signature_request(
        self,
        signer_email: str,
        signer_name: str,
        landlord_name: str,
        property_address: str,
        signing_link: str,
        kaution_amount: float,
        language: str = "de",
    ) -> EmailSendResponse:
        """Send signature request email.

        Args:
            signer_email: Signer email address
            signer_name: Signer name
            landlord_name: Landlord name
            property_address: Property address
            signing_link: Magic link for signing
            kaution_amount: Deposit amount
            language: Email language

        Returns:
            EmailSendResponse
        """
        variables = {
            "signer_name": signer_name,
            "signer_email": signer_email,
            "landlord_name": landlord_name,
            "property_address": property_address,
            "signing_link": signing_link,
            "kaution_amount": f"{kaution_amount:,.2f}",
            "unsubscribe_link": f"{settings.signing_base_url}/unsubscribe",
        }

        return await self.send_email(
            to_email=signer_email,
            to_name=signer_name,
            template_key="signature_request",
            variables=variables,
            language=language,
        )

    async def send_signature_completed(
        self,
        recipient_email: str,
        recipient_name: str,
        property_address: str,
        signers: list[dict[str, str]],
        download_link: str,
        language: str = "de",
    ) -> EmailSendResponse:
        """Send signature completed confirmation email.

        Args:
            recipient_email: Recipient email
            recipient_name: Recipient name
            property_address: Property address
            signers: List of signers with name, role, signed_at
            download_link: Link to download signed contract
            language: Email language

        Returns:
            EmailSendResponse
        """
        variables = {
            "recipient_name": recipient_name,
            "property_address": property_address,
            "signers": signers,
            "download_link": download_link,
        }

        return await self.send_email(
            to_email=recipient_email,
            to_name=recipient_name,
            template_key="signature_completed",
            variables=variables,
            language=language,
        )

    async def send_signature_reminder(
        self,
        signer_email: str,
        signer_name: str,
        landlord_name: str,
        property_address: str,
        signing_link: str,
        expires_at: str,
        language: str = "de",
    ) -> EmailSendResponse:
        """Send signature reminder email.

        Args:
            signer_email: Signer email
            signer_name: Signer name
            landlord_name: Landlord name
            property_address: Property address
            signing_link: Magic link for signing
            expires_at: Expiration datetime
            language: Email language

        Returns:
            EmailSendResponse
        """
        variables = {
            "signer_name": signer_name,
            "landlord_name": landlord_name,
            "property_address": property_address,
            "signing_link": signing_link,
            "expires_at": expires_at,
        }

        return await self.send_email(
            to_email=signer_email,
            to_name=signer_name,
            template_key="signature_reminder",
            variables=variables,
            language=language,
        )
