"""Email template database model."""

from datetime import datetime
from typing import Optional
from uuid import UUID


class EmailTemplate:
    """Email template model."""

    def __init__(
        self,
        id: UUID,
        tenant_id: Optional[UUID],
        template_key: str,
        name: str,
        description: Optional[str],
        subject_template: str,
        body_html: str,
        body_text: str,
        language: str = "de",
        is_default: bool = False,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        updated_by: Optional[UUID] = None,
    ):
        """Initialize email template."""
        self.id = id
        self.tenant_id = tenant_id
        self.template_key = template_key
        self.name = name
        self.description = description
        self.subject_template = subject_template
        self.body_html = body_html
        self.body_text = body_text
        self.language = language
        self.is_default = is_default
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at
        self.updated_by = updated_by

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "template_key": self.template_key,
            "name": self.name,
            "description": self.description,
            "subject_template": self.subject_template,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "language": self.language,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": str(self.updated_by) if self.updated_by else None,
        }
