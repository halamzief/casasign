"""Tests for section override schemas."""

import pytest
from pydantic import ValidationError

from src.schemas.signature import SectionSchema


class TestSectionSchema:
    """Test SectionSchema validation and HTML sanitization."""

    def test_default_section(self) -> None:
        s = SectionSchema(sort_order=1, title="Vermieter", section_key="vermieter")
        assert s.custom_html is None
        assert s.section_key == "vermieter"

    def test_override_section(self) -> None:
        s = SectionSchema(
            sort_order=7,
            title="Schönheitsreparaturen",
            section_key="schoenheitsreparaturen",
            custom_html="<p>Renovierung nach 10 Jahren</p>",
        )
        assert s.custom_html == "<p>Renovierung nach 10 Jahren</p>"

    def test_custom_section_no_key(self) -> None:
        s = SectionSchema(
            sort_order=17,
            title="Gartennutzung",
            custom_html="<p>Mieter pflegt Garten</p>",
        )
        assert s.section_key is None
        assert s.title == "Gartennutzung"

    def test_html_sanitization_strips_script(self) -> None:
        """Defense-in-depth: script tags must be stripped."""
        s = SectionSchema(
            sort_order=1,
            title="Test",
            custom_html='<p>Safe</p><script>alert("xss")</script>',
        )
        assert "<script>" not in s.custom_html
        assert "<p>Safe</p>" in s.custom_html

    def test_html_sanitization_strips_onclick(self) -> None:
        """Event handlers must be stripped."""
        s = SectionSchema(
            sort_order=1,
            title="Test",
            custom_html='<p onclick="alert(1)">Text</p>',
        )
        assert "onclick" not in s.custom_html
        assert "<p>" in s.custom_html

    def test_html_sanitization_allows_formatting(self) -> None:
        """Bold, italic, lists should be preserved."""
        html = "<p><strong>Bold</strong> and <em>italic</em></p><ul><li>Item</li></ul>"
        s = SectionSchema(sort_order=1, title="Test", custom_html=html)
        assert "<strong>Bold</strong>" in s.custom_html
        assert "<em>italic</em>" in s.custom_html
        assert "<ul><li>Item</li></ul>" in s.custom_html

    def test_none_custom_html_passes(self) -> None:
        s = SectionSchema(sort_order=1, title="Test")
        assert s.custom_html is None

    def test_zero_sort_order_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SectionSchema(sort_order=0, title="Test")

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SectionSchema(sort_order=1, title="")
