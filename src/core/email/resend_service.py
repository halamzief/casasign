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
