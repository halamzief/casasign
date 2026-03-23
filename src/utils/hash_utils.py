"""Hashing utilities for document integrity."""

import base64
import hashlib


def calculate_sha256(content: bytes) -> str:
    """Calculate SHA-256 hash of content.

    Args:
        content: Binary content to hash

    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256(content)
    return sha256_hash.hexdigest()


def calculate_sha256_from_base64(base64_content: str) -> str:
    """Calculate SHA-256 hash from base64-encoded content.

    Args:
        base64_content: Base64-encoded content

    Returns:
        Hexadecimal hash string
    """
    content = base64.b64decode(base64_content)
    return calculate_sha256(content)


def verify_document_hash(content: bytes, expected_hash: str) -> bool:
    """Verify document hash matches expected value.

    Args:
        content: Binary content
        expected_hash: Expected SHA-256 hash

    Returns:
        True if hash matches, False otherwise
    """
    actual_hash = calculate_sha256(content)
    return actual_hash == expected_hash
