"""Tests for attachment handling in signing requests."""

import base64

import pytest
from pydantic import ValidationError

from src.schemas.signature import AttachmentSchema


class TestAttachmentSchema:
    """Test AttachmentSchema validation."""

    def test_valid_attachment(self) -> None:
        att = AttachmentSchema(
            filename="Hausordnung.pdf",
            content_base64=base64.b64encode(b"%PDF-1.4 test").decode(),
            size_bytes=14,
        )
        assert att.filename == "Hausordnung.pdf"
        assert att.size_bytes == 14

    def test_empty_filename_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AttachmentSchema(filename="", content_base64="abc", size_bytes=1)

    def test_empty_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AttachmentSchema(filename="test.pdf", content_base64="", size_bytes=1)

    def test_zero_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AttachmentSchema(filename="test.pdf", content_base64="abc", size_bytes=0)

    def test_negative_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AttachmentSchema(filename="test.pdf", content_base64="abc", size_bytes=-1)
