"""Application configuration management."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service Configuration
    service_name: str = "signcasa-signatures"
    service_port: int = 9000
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/signcasa

    # Email Service (Resend)
    resend_api_key: str
    from_email: str = "signatures@signcasa.de"
    from_name: str = "SignCasa Signatures"

    # Signature Configuration
    signature_expiry_days: int = 7
    signing_base_url: str = "https://sign.signcasa.de"
    backend_url: str = os.getenv("BACKEND_URL", "http://fes-service:9000")
    callback_timeout_seconds: int = 30

    # File Storage
    signatures_storage_path: str = "./storage/signatures"
    max_pdf_size_mb: int = 10

    # Security
    secret_key: str
    allowed_origins: str = "http://localhost:5174,https://app.signcasa.de"

    # Webhook
    webhook_secret: str = ""

    # WhatsApp Business (Premium Feature - Optional)
    whatsapp_business_enabled: bool = False
    whatsapp_api_url: str = "https://graph.facebook.com/v18.0"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""

    # Monitoring (Optional)
    sentry_dsn: str = ""
    sentry_environment: str = "development"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse allowed origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def max_pdf_size_bytes(self) -> int:
        """Convert max PDF size from MB to bytes."""
        return self.max_pdf_size_mb * 1024 * 1024


# Global settings instance
settings = Settings()
