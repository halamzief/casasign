"""Signature request database models."""

from datetime import datetime
from typing import Optional
from uuid import UUID


class SignatureRequest:
    """Signature request model.

    Supports three document modes:
    - PDF mode (document_type='pdf'): Uses document_url and document_hash
    - JSON mode (document_type='json'): Uses contract_data, generates PDF at completion
    - HTML mode (document_type='html'): Uses document_html, pre-rendered by caller
    """

    def __init__(
        self,
        id: UUID,
        contract_id: UUID,
        requester_user_id: UUID,
        requester_email: str,
        tenant_id: UUID,
        # Document fields - nullable for JSON mode
        document_hash: Optional[str] = None,
        document_url: Optional[str] = None,
        # JSON mode fields
        contract_data: Optional[dict] = None,
        document_type: str = "pdf",  # 'pdf', 'json', or 'html'
        pdf_generated_at: Optional[datetime] = None,
        # HTML mode fields
        document_html: Optional[str] = None,
        # Attachments
        attachments: Optional[list] = None,
        # Metadata
        document_title: Optional[str] = None,
        document_name: Optional[str] = None,
        sender_name: Optional[str] = None,
        # Status tracking
        status: str = "pending",
        expires_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        callback_url: Optional[str] = None,
        custom_email_template_id: Optional[UUID] = None,
    ):
        """Initialize signature request."""
        self.id = id
        self.contract_id = contract_id
        self.document_hash = document_hash
        self.document_url = document_url
        self.contract_data = contract_data
        self.document_type = document_type
        self.pdf_generated_at = pdf_generated_at
        self.document_html = document_html
        self.attachments = attachments
        self.document_title = document_title
        self.document_name = document_name
        self.sender_name = sender_name
        self.requester_user_id = requester_user_id
        self.requester_email = requester_email
        self.tenant_id = tenant_id
        self.status = status
        self.expires_at = expires_at
        self.created_at = created_at
        self.completed_at = completed_at
        self.callback_url = callback_url
        self.custom_email_template_id = custom_email_template_id

    @property
    def is_json_mode(self) -> bool:
        """Check if this request uses JSON-to-HTML mode."""
        return self.document_type == "json"

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "contract_id": str(self.contract_id),
            "document_hash": self.document_hash,
            "document_url": self.document_url,
            "contract_data": self.contract_data,
            "document_type": self.document_type,
            "pdf_generated_at": (
                self.pdf_generated_at.isoformat() if self.pdf_generated_at else None
            ),
            "attachments": self.attachments,
            "requester_user_id": str(self.requester_user_id),
            "requester_email": self.requester_email,
            "tenant_id": str(self.tenant_id),
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "callback_url": self.callback_url,
            "custom_email_template_id": (
                str(self.custom_email_template_id) if self.custom_email_template_id else None
            ),
        }


class SignatureSigner:
    """Signature signer model."""

    def __init__(
        self,
        id: UUID,
        request_id: UUID,
        name: str,
        email: str,
        role: str,
        signing_order: int,
        verification_token: str,
        phone: Optional[str] = None,
        verification_method: str = "email_link",
        signed_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        geolocation: Optional[dict] = None,
        signature_image_base64: Optional[str] = None,
        consents: Optional[dict] = None,
    ):
        """Initialize signer."""
        self.id = id
        self.request_id = request_id
        self.name = name
        self.email = email
        self.role = role
        self.signing_order = signing_order
        self.verification_token = verification_token
        self.phone = phone
        self.verification_method = verification_method
        self.signed_at = signed_at
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.geolocation = geolocation
        self.signature_image_base64 = signature_image_base64
        self.consents = consents

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "request_id": str(self.request_id),
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "signing_order": self.signing_order,
            "verification_token": self.verification_token,
            "phone": self.phone,
            "verification_method": self.verification_method,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "geolocation": self.geolocation,
            "signature_image_base64": self.signature_image_base64,
            "consents": self.consents,
        }


class SignatureAuditLog:
    """Signature audit log model."""

    def __init__(
        self,
        id: UUID,
        request_id: UUID,
        event_type: str,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict] = None,
        created_at: Optional[datetime] = None,
    ):
        """Initialize audit log entry."""
        self.id = id
        self.request_id = request_id
        self.event_type = event_type
        self.actor_email = actor_email
        self.actor_role = actor_role
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.metadata = metadata
        self.created_at = created_at

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "request_id": str(self.request_id),
            "event_type": self.event_type,
            "actor_email": self.actor_email,
            "actor_role": self.actor_role,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
