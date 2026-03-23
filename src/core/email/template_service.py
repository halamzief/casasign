"""Email template rendering service with Jinja2."""

from typing import Any, Optional
from uuid import UUID

from jinja2 import Environment, Template, TemplateSyntaxError
from loguru import logger

from src.core.repositories.email_template_repository import EmailTemplateRepository
from src.schemas.email import EmailRenderResponse


class EmailTemplateService:
    """Service for rendering email templates with Jinja2."""

    def __init__(self, template_repository: EmailTemplateRepository):
        """Initialize service with template repository."""
        self.repository = template_repository
        self.jinja_env = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)

    async def render_template(
        self,
        template_key: str,
        variables: dict[str, Any],
        language: str = "de",
        tenant_id: Optional[UUID] = None,
    ) -> EmailRenderResponse:
        """Render email template with variables.

        Args:
            template_key: Template identifier
            variables: Template variables for Jinja2 rendering
            language: Template language
            tenant_id: Optional tenant ID for custom templates

        Returns:
            EmailRenderResponse with rendered subject and body

        Raises:
            ValueError: If template not found or rendering fails
        """
        logger.info(
            "Rendering email template",
            template_key=template_key,
            language=language,
            tenant_id=tenant_id,
        )

        # Fetch template from database
        template = await self.repository.get_by_key(template_key, language, tenant_id)

        if not template:
            raise ValueError(f"Email template not found: {template_key} ({language})")

        try:
            # Render subject
            subject_template: Template = self.jinja_env.from_string(template.subject_template)
            subject = subject_template.render(**variables)

            # Render HTML body
            html_template: Template = self.jinja_env.from_string(template.body_html)
            body_html = html_template.render(**variables)

            # Render plain text body
            text_template: Template = self.jinja_env.from_string(template.body_text)
            body_text = text_template.render(**variables)

            logger.success("Template rendered successfully", template_key=template_key)

            return EmailRenderResponse(
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                template_key=template_key,
            )

        except TemplateSyntaxError as e:
            logger.error("Template syntax error", template_key=template_key, error=str(e))
            raise ValueError(f"Template syntax error: {e}") from e

        except Exception as e:
            logger.error("Template rendering failed", template_key=template_key, error=str(e))
            raise ValueError(f"Template rendering failed: {e}") from e

    def validate_template(self, template_content: str) -> tuple[bool, Optional[str]]:
        """Validate Jinja2 template syntax.

        Args:
            template_content: Template string to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.jinja_env.from_string(template_content)
            return True, None
        except TemplateSyntaxError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Validation error: {e}"
