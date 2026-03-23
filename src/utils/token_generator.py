"""Secure token generation for signature requests."""

import secrets
import string


def generate_verification_token(length: int = 64) -> str:
    """Generate a cryptographically secure verification token.

    Args:
        length: Token length (default: 64 characters)

    Returns:
        URL-safe token string
    """
    # Use URL-safe characters (alphanumeric + - and _)
    alphabet = string.ascii_letters + string.digits + "-_"
    token = "".join(secrets.choice(alphabet) for _ in range(length))
    return token


def generate_short_code(length: int = 8) -> str:
    """Generate a short verification code (for SMS/WhatsApp).

    Args:
        length: Code length (default: 8 characters)

    Returns:
        Alphanumeric code
    """
    alphabet = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(length))
    return code
