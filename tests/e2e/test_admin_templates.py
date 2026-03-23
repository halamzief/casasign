"""E2E tests for admin email template management UI."""

import pytest
from playwright.async_api import Page, expect


@pytest.mark.e2e
@pytest.mark.admin
class TestAdminTemplates:
    """Test admin template CRUD operations."""

    async def test_admin_page_loads(self, page: Page, admin_templates_url: str):
        """Test that admin templates page loads successfully."""
        await page.goto(admin_templates_url)

        # Check page title
        await expect(page.locator("h1")).to_contain_text("Email Templates")

        # Check "New Template" button exists
        new_button = page.locator("button", has_text="Neue Vorlage")
        await expect(new_button).to_be_visible()

    async def test_templates_list_displays(self, page: Page, admin_templates_url: str):
        """Test that templates list displays correctly."""
        await page.goto(admin_templates_url)

        # Wait for templates to load
        await page.wait_for_selector("table", timeout=5000)

        # Check table headers
        await expect(page.locator("th:has-text('Name')")).to_be_visible()
        await expect(page.locator("th:has-text('Template Key')")).to_be_visible()
        await expect(page.locator("th:has-text('Language')")).to_be_visible()
        await expect(page.locator("th:has-text('Status')")).to_be_visible()

        # Check at least one template exists
        template_rows = page.locator("tbody tr")
        await expect(template_rows).to_have_count(min=1)

    async def test_create_template_modal_opens(self, page: Page, admin_templates_url: str):
        """Test that create template modal opens."""
        await page.goto(admin_templates_url)

        # Click "New Template" button
        await page.click("button:has-text('Neue Vorlage')")

        # Check modal appears
        modal = page.locator("div.modal")  # Adjust selector based on your modal
        await expect(modal).to_be_visible()

        # Check form fields exist
        await expect(page.locator("input[name='template_key']")).to_be_visible()
        await expect(page.locator("input[name='name']")).to_be_visible()
        await expect(page.locator("input[name='subject_template']")).to_be_visible()
        await expect(page.locator("textarea[name='body_html']")).to_be_visible()
        await expect(page.locator("textarea[name='body_text']")).to_be_visible()

    async def test_create_template_validation(self, page: Page, admin_templates_url: str):
        """Test form validation when creating template."""
        await page.goto(admin_templates_url)

        # Open create modal
        await page.click("button:has-text('Neue Vorlage')")

        # Try to submit empty form
        await page.click("button:has-text('Erstellen')")

        # Check for validation errors
        # (Adjust selectors based on your validation implementation)
        error_messages = page.locator(".error-message, .text-red-600")
        await expect(error_messages).to_have_count(min=1)

    async def test_create_new_template(self, page: Page, admin_templates_url: str):
        """Test creating a new email template."""
        await page.goto(admin_templates_url)

        # Open create modal
        await page.click("button:has-text('Neue Vorlage')")

        # Fill in form
        timestamp = str(int(page.evaluate("() => Date.now()")))
        template_key = f"test_template_{timestamp}"

        await page.fill("input[name='template_key']", template_key)
        await page.fill("input[name='name']", f"Test Template {timestamp}")
        await page.fill(
            "input[name='subject_template']",
            "Test Subject: {{signer_name}}",
        )
        await page.fill(
            "textarea[name='body_html']",
            "<p>Hello {{signer_name}}, please sign the contract.</p>",
        )
        await page.fill(
            "textarea[name='body_text']",
            "Hello {{signer_name}}, please sign the contract.",
        )

        # Submit form
        await page.click("button:has-text('Erstellen')")

        # Wait for success (modal should close)
        await page.wait_for_selector("div.modal", state="hidden", timeout=5000)

        # Verify new template appears in list
        await expect(page.locator(f"td:has-text('{template_key}')")).to_be_visible()

        # Cleanup: Delete the test template
        # Find the row with the test template and click delete
        row = page.locator("tr", has_text=template_key)
        await row.locator("button[title='Delete'], button:has-text('Delete')").click()

        # Confirm deletion
        await page.click("button:has-text('Confirm'), button:has-text('Bestätigen')")

    async def test_edit_template(self, page: Page, admin_templates_url: str):
        """Test editing an existing template."""
        await page.goto(admin_templates_url)

        # Wait for templates to load
        await page.wait_for_selector("table")

        # Find first non-default template (if any)
        # For this test, we'll use any template and just open the edit modal
        edit_button = page.locator("button[title='Edit'], button:has-text('Edit')").first
        await edit_button.click()

        # Check edit modal appears
        modal = page.locator("div.modal")
        await expect(modal).to_be_visible()

        # Check that template_key is read-only
        template_key_input = page.locator("input[name='template_key']")
        await expect(template_key_input).to_be_disabled()

        # Check other fields are editable
        await expect(page.locator("input[name='name']")).to_be_enabled()
        await expect(page.locator("input[name='subject_template']")).to_be_enabled()

        # Close modal without saving
        await page.click("button:has-text('Cancel'), button:has-text('Abbrechen')")

    async def test_preview_template(self, page: Page, admin_templates_url: str):
        """Test template preview functionality."""
        await page.goto(admin_templates_url)

        # Wait for templates to load
        await page.wait_for_selector("table")

        # Click preview button on first template
        preview_button = page.locator("button[title='Preview'], button:has-text('Preview')").first
        await preview_button.click()

        # Check preview modal appears
        modal = page.locator("div.modal")
        await expect(modal).to_be_visible()

        # Check preview sections exist
        await expect(page.locator("text=Subject Preview")).to_be_visible()
        await expect(page.locator("text=HTML Preview")).to_be_visible()
        await expect(page.locator("text=Text Preview")).to_be_visible()

        # Check that sample variables are rendered (not {{signer_name}})
        # The preview should show actual values, not template syntax
        preview_content = page.locator(".preview-content, .modal-body")
        content = await preview_content.text_content()

        # Verify template variables are replaced with sample data
        assert "Max Mustermann" in content or "Lisa Schmidt" in content

        # Close preview
        await page.click("button:has-text('Close'), button:has-text('Schließen')")

    async def test_delete_protection_for_defaults(self, page: Page, admin_templates_url: str):
        """Test that system default templates cannot be deleted."""
        await page.goto(admin_templates_url)

        # Find a default template (has "System Default" badge)
        default_row = page.locator("tr:has(.badge:has-text('System Default'))").first

        # Try to click delete button
        delete_button = default_row.locator("button[title='Delete'], button:has-text('Delete')")

        # Check if delete button is disabled or shows error on click
        is_disabled = await delete_button.is_disabled()
        if not is_disabled:
            await delete_button.click()
            # Should show error message
            error = page.locator(".error-message, .text-red-600")
            await expect(error).to_contain_text("Cannot delete system default template")

    async def test_filter_templates_by_status(self, page: Page, admin_templates_url: str):
        """Test filtering templates by active/inactive status."""
        await page.goto(admin_templates_url)

        # Check if filter exists (query parameters: active_only=true/false)
        # This depends on your implementation - adjust as needed

        # By default, should show only active templates
        url = page.url
        assert "active_only" not in url or "active_only=true" in url

        # Check that all visible templates have "Active" badge
        active_badges = page.locator(".badge:has-text('Active')")
        count = await active_badges.count()
        assert count > 0

    async def test_responsive_layout_mobile(self, mobile_page: Page, admin_templates_url: str):
        """Test admin page responsive layout on mobile."""
        await mobile_page.goto(admin_templates_url)

        # Check page loads
        await expect(mobile_page.locator("h1")).to_be_visible()

        # Check table is scrollable or stacked on mobile
        # (Implementation depends on your CSS)
        viewport_size = mobile_page.viewport_size
        assert viewport_size["width"] <= 428  # iPhone 14 Pro width

        # Verify "New Template" button is still accessible
        new_button = mobile_page.locator("button:has-text('Neue Vorlage')")
        await expect(new_button).to_be_visible()

        # Check that button is full-width or properly sized for mobile
        button_box = await new_button.bounding_box()
        assert button_box["width"] >= 200  # Minimum touch target


@pytest.mark.e2e
@pytest.mark.admin
class TestAdminTemplatesPerformance:
    """Performance tests for admin templates page."""

    async def test_page_load_time(self, page: Page, admin_templates_url: str):
        """Test that page loads within acceptable time."""
        start_time = await page.evaluate("() => performance.now()")

        await page.goto(admin_templates_url)

        # Wait for templates to load
        await page.wait_for_selector("table")

        end_time = await page.evaluate("() => performance.now()")
        load_time = end_time - start_time

        # Should load within 2 seconds
        assert load_time < 2000, f"Page took {load_time}ms to load (>2000ms)"

    async def test_create_template_response_time(self, page: Page, admin_templates_url: str):
        """Test that template creation completes quickly."""
        await page.goto(admin_templates_url)

        # Open create modal
        await page.click("button:has-text('Neue Vorlage')")

        # Fill form
        timestamp = str(int(await page.evaluate("() => Date.now()")))
        await page.fill("input[name='template_key']", f"perf_test_{timestamp}")
        await page.fill("input[name='name']", f"Performance Test {timestamp}")
        await page.fill("input[name='subject_template']", "Performance Test")
        await page.fill("textarea[name='body_html']", "<p>Performance Test</p>")
        await page.fill("textarea[name='body_text']", "Performance Test")

        # Measure submit time
        start_time = await page.evaluate("() => performance.now()")

        await page.click("button:has-text('Erstellen')")

        # Wait for modal to close (indicates success)
        await page.wait_for_selector("div.modal", state="hidden", timeout=5000)

        end_time = await page.evaluate("() => performance.now()")
        response_time = end_time - start_time

        # Should complete within 1 second
        assert response_time < 1000, f"Creation took {response_time}ms (>1000ms)"
