"""Admin API endpoints for email template management."""

import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.email_template_repository import EmailTemplateRepository
from src.database.session import get_db_session
from src.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateResponse,
    EmailTemplateUpdate,
)


async def require_admin_key(x_admin_key: str = Header(...)) -> None:
    """Validate admin API key from request header."""
    expected = os.getenv("FES_ADMIN_KEY", "")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Invalid admin key")


router = APIRouter(
    prefix="/api/admin/templates",
    tags=["Admin - Email Templates"],
    dependencies=[Depends(require_admin_key)],
)


async def get_email_template_repository(
    session: AsyncSession = Depends(get_db_session),
) -> EmailTemplateRepository:
    """Dependency: Get email template repository."""
    return EmailTemplateRepository(session)


@router.get("", response_model=list[EmailTemplateResponse])
async def list_email_templates(
    tenant_id: Optional[UUID] = Query(None, description="Filter by tenant ID"),
    active_only: bool = Query(True, description="Show only active templates"),
    repo: EmailTemplateRepository = Depends(get_email_template_repository),
) -> list[EmailTemplateResponse]:
    """List all email templates.

    Args:
        tenant_id: Optional tenant ID filter
        active_only: Show only active templates (default: true)
        repo: Email template repository dependency

    Returns:
        List of email templates
    """
    logger.info(
        "API: Listing email templates",
        tenant_id=tenant_id,
        active_only=active_only,
    )

    try:
        templates = await repo.list_templates(tenant_id=tenant_id, active_only=active_only)

        # Convert to response format
        return [
            EmailTemplateResponse(
                id=t.id,
                tenant_id=t.tenant_id,
                template_key=t.template_key,
                name=t.name,
                description=t.description,
                subject_template=t.subject_template,
                body_html=t.body_html,
                body_text=t.body_text,
                language=t.language,
                is_default=t.is_default,
                is_active=t.is_active,
                created_at=t.created_at
                if isinstance(t.created_at, str)
                else (t.created_at.isoformat() if t.created_at else ""),
                updated_at=t.updated_at
                if isinstance(t.updated_at, str)
                else (t.updated_at.isoformat() if t.updated_at else ""),
                updated_by=t.updated_by,
            )
            for t in templates
        ]

    except Exception as e:
        logger.error("API: Failed to list templates", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}") from e


@router.get("/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: UUID,
    repo: EmailTemplateRepository = Depends(get_email_template_repository),
) -> EmailTemplateResponse:
    """Get a specific email template by ID.

    Args:
        template_id: Template ID
        repo: Email template repository dependency

    Returns:
        Email template details

    Raises:
        HTTPException: If template not found
    """
    logger.info("API: Getting email template", template_id=str(template_id))

    try:
        template = await repo.get_by_id(template_id)

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return EmailTemplateResponse(
            id=template.id,
            tenant_id=template.tenant_id,
            template_key=template.template_key,
            name=template.name,
            description=template.description,
            subject_template=template.subject_template,
            body_html=template.body_html,
            body_text=template.body_text,
            language=template.language,
            is_default=template.is_default,
            is_active=template.is_active,
            created_at=template.created_at.isoformat() if template.created_at else "",
            updated_at=template.updated_at.isoformat() if template.updated_at else "",
            updated_by=template.updated_by,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("API: Failed to get template", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get template") from e


@router.post("", response_model=EmailTemplateResponse, status_code=201)
async def create_email_template(
    template_data: EmailTemplateCreate,
    repo: EmailTemplateRepository = Depends(get_email_template_repository),
) -> EmailTemplateResponse:
    """Create a new email template.

    Args:
        template_data: Template creation data
        repo: Email template repository dependency

    Returns:
        Created template

    Raises:
        HTTPException: If creation fails or duplicate template exists
    """
    logger.info(
        "API: Creating email template",
        template_key=template_data.template_key,
        language=template_data.language,
    )

    try:
        template = await repo.create_template(
            template_key=template_data.template_key,
            name=template_data.name,
            subject_template=template_data.subject_template,
            body_html=template_data.body_html,
            body_text=template_data.body_text,
            description=template_data.description,
            language=template_data.language,
            tenant_id=template_data.tenant_id,
            is_default=template_data.is_default,
        )

        return EmailTemplateResponse(
            id=template.id,
            tenant_id=template.tenant_id,
            template_key=template.template_key,
            name=template.name,
            description=template.description,
            subject_template=template.subject_template,
            body_html=template.body_html,
            body_text=template.body_text,
            language=template.language,
            is_default=template.is_default,
            is_active=template.is_active,
            created_at=template.created_at.isoformat() if template.created_at else "",
            updated_at=template.updated_at.isoformat() if template.updated_at else "",
            updated_by=template.updated_by,
        )

    except ValueError as e:
        logger.error("API: Validation error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("API: Failed to create template", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create template") from e


@router.put("/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: UUID,
    template_data: EmailTemplateUpdate,
    repo: EmailTemplateRepository = Depends(get_email_template_repository),
) -> EmailTemplateResponse:
    """Update an existing email template.

    Args:
        template_id: Template ID to update
        template_data: Template update data
        repo: Email template repository dependency

    Returns:
        Updated template

    Raises:
        HTTPException: If update fails or template not found
    """
    logger.info("API: Updating email template", template_id=str(template_id))

    try:
        template = await repo.update_template(
            template_id=template_id,
            name=template_data.name,
            description=template_data.description,
            subject_template=template_data.subject_template,
            body_html=template_data.body_html,
            body_text=template_data.body_text,
            is_active=template_data.is_active,
        )

        return EmailTemplateResponse(
            id=template.id,
            tenant_id=template.tenant_id,
            template_key=template.template_key,
            name=template.name,
            description=template.description,
            subject_template=template.subject_template,
            body_html=template.body_html,
            body_text=template.body_text,
            language=template.language,
            is_default=template.is_default,
            is_active=template.is_active,
            created_at=template.created_at.isoformat() if template.created_at else "",
            updated_at=template.updated_at.isoformat() if template.updated_at else "",
            updated_by=template.updated_by,
        )

    except ValueError as e:
        logger.error("API: Validation error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("API: Failed to update template", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update template") from e


@router.delete("/{template_id}", status_code=204)
async def delete_email_template(
    template_id: UUID,
    repo: EmailTemplateRepository = Depends(get_email_template_repository),
) -> None:
    """Delete an email template (soft delete).

    Args:
        template_id: Template ID to delete
        repo: Email template repository dependency

    Raises:
        HTTPException: If deletion fails or template not found
    """
    logger.info("API: Deleting email template", template_id=str(template_id))

    try:
        await repo.delete_template(template_id)
        logger.success("API: Template deleted", template_id=str(template_id))

    except ValueError as e:
        logger.error("API: Validation error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("API: Failed to delete template", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete template") from e
