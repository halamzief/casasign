"""Email template repository for PostgreSQL database operations."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.email_template import EmailTemplateRow
from src.models.email_template import EmailTemplate


class EmailTemplateRepository:
    """Repository for email template database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def get_by_key(
        self, template_key: str, language: str = "de", tenant_id: Optional[UUID] = None
    ) -> Optional[EmailTemplate]:
        """Get email template by key and language with tenant fallback."""
        logger.debug(
            "Fetching email template",
            template_key=template_key,
            language=language,
            tenant_id=tenant_id,
        )

        # Try tenant-specific template first
        if tenant_id:
            stmt = (
                select(EmailTemplateRow)
                .where(EmailTemplateRow.template_key == template_key)
                .where(EmailTemplateRow.language == language)
                .where(EmailTemplateRow.tenant_id == str(tenant_id))
                .where(EmailTemplateRow.is_active.is_(True))
            )
            result = await self.session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                logger.info("Found tenant-specific template", tenant_id=tenant_id)
                return self._row_to_model(row)

        # Fall back to default template
        stmt = (
            select(EmailTemplateRow)
            .where(EmailTemplateRow.template_key == template_key)
            .where(EmailTemplateRow.language == language)
            .where(EmailTemplateRow.tenant_id.is_(None))
            .where(EmailTemplateRow.is_active.is_(True))
            .where(EmailTemplateRow.is_default.is_(True))
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            logger.info("Found default template")
            return self._row_to_model(row)

        logger.warning("Template not found", template_key=template_key, language=language)
        return None

    async def get_by_id(self, template_id: UUID) -> Optional[EmailTemplate]:
        """Get email template by ID."""
        stmt = select(EmailTemplateRow).where(EmailTemplateRow.id == str(template_id))
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            return self._row_to_model(row)
        return None

    async def list_templates(
        self, tenant_id: Optional[UUID] = None, active_only: bool = True
    ) -> list[EmailTemplate]:
        """List all email templates."""
        stmt = select(EmailTemplateRow)

        if tenant_id:
            stmt = stmt.where(EmailTemplateRow.tenant_id == str(tenant_id))

        if active_only:
            stmt = stmt.where(EmailTemplateRow.is_active.is_(True))

        stmt = stmt.order_by(EmailTemplateRow.created_at.desc())
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return [self._row_to_model(row) for row in rows]

    async def create_template(
        self,
        template_key: str,
        name: str,
        subject_template: str,
        body_html: str,
        body_text: str,
        description: Optional[str] = None,
        language: str = "de",
        tenant_id: Optional[UUID] = None,
        is_default: bool = False,
        created_by: Optional[UUID] = None,
    ) -> EmailTemplate:
        """Create a new email template."""
        logger.info(
            "Creating email template",
            template_key=template_key,
            language=language,
            tenant_id=tenant_id,
        )

        # Check for duplicate
        existing = await self.get_by_key(template_key, language, tenant_id)
        if existing:
            raise ValueError(f"Template '{template_key}' with language '{language}' already exists")

        row = EmailTemplateRow(
            template_key=template_key,
            name=name,
            description=description,
            subject_template=subject_template,
            body_html=body_html,
            body_text=body_text,
            language=language,
            tenant_id=str(tenant_id) if tenant_id else None,
            is_default=is_default,
            is_active=True,
            updated_by=str(created_by) if created_by else None,
        )
        self.session.add(row)
        await self.session.flush()

        logger.success("Email template created", template_id=row.id)
        return self._row_to_model(row)

    async def update_template(
        self,
        template_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        subject_template: Optional[str] = None,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        is_active: Optional[bool] = None,
        updated_by: Optional[UUID] = None,
    ) -> EmailTemplate:
        """Update an existing email template."""
        logger.info("Updating email template", template_id=str(template_id))

        values: dict = {"updated_at": datetime.now(timezone.utc)}

        if name is not None:
            values["name"] = name
        if description is not None:
            values["description"] = description
        if subject_template is not None:
            values["subject_template"] = subject_template
        if body_html is not None:
            values["body_html"] = body_html
        if body_text is not None:
            values["body_text"] = body_text
        if is_active is not None:
            values["is_active"] = is_active
        if updated_by is not None:
            values["updated_by"] = str(updated_by)

        stmt = (
            update(EmailTemplateRow)
            .where(EmailTemplateRow.id == str(template_id))
            .values(**values)
            .returning(EmailTemplateRow)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if not row:
            raise ValueError(f"Template with ID {template_id} not found")

        logger.success("Email template updated", template_id=str(template_id))
        return self._row_to_model(row)

    async def delete_template(self, template_id: UUID) -> bool:
        """Soft delete an email template."""
        logger.info("Deleting email template", template_id=str(template_id))

        template = await self.get_by_id(template_id)
        if not template:
            raise ValueError(f"Template with ID {template_id} not found")

        if template.is_default:
            raise ValueError("Cannot delete system default template")

        stmt = (
            update(EmailTemplateRow)
            .where(EmailTemplateRow.id == str(template_id))
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)

        logger.success("Email template deleted", template_id=str(template_id))
        return True

    def _row_to_model(self, row: EmailTemplateRow) -> EmailTemplate:
        """Convert SQLAlchemy row to domain model."""
        return EmailTemplate(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id) if row.tenant_id else None,
            template_key=row.template_key,
            name=row.name,
            description=row.description,
            subject_template=row.subject_template,
            body_html=row.body_html,
            body_text=row.body_text,
            language=row.language,
            is_default=row.is_default,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
            updated_by=UUID(row.updated_by) if row.updated_by else None,
        )
