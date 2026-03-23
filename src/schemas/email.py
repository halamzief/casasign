"""Email template Pydantic schemas."""

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class EmailTemplateBase(BaseModel):
    """Base email template schema."""

    template_key: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    subject_template: str
    body_html: str
    body_text: str
    language: str = Field(default="de", max_length=5)
    is_default: bool = False
    is_active: bool = True


class EmailTemplateCreate(EmailTemplateBase):
    """Schema for creating email template."""

    tenant_id: Optional[UUID] = None


class EmailTemplateUpdate(BaseModel):
    """Schema for updating email template."""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    subject_template: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    is_active: Optional[bool] = None


class EmailTemplateResponse(EmailTemplateBase):
    """Schema for email template response."""

    id: UUID
    tenant_id: Optional[UUID]
    created_at: str
    updated_at: str
    updated_by: Optional[UUID]

    class Config:
        """Pydantic config."""

        from_attributes = True


class EmailRenderRequest(BaseModel):
    """Schema for email rendering request."""

    template_key: str
    language: str = "de"
    tenant_id: Optional[UUID] = None
    variables: dict[str, Any] = Field(default_factory=dict)


class EmailRenderResponse(BaseModel):
    """Schema for rendered email."""

    subject: str
    body_html: str
    body_text: str
    template_key: str


class EmailSendRequest(BaseModel):
    """Schema for sending email."""

    to_email: EmailStr
    to_name: str
    template_key: str
    language: str = "de"
    tenant_id: Optional[UUID] = None
    variables: dict[str, Any] = Field(default_factory=dict)


class EmailSendResponse(BaseModel):
    """Schema for email send response."""

    success: bool
    message: str
    email_id: Optional[str] = None
