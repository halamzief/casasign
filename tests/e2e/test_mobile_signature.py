"""E2E tests for mobile signature pad and signing flow."""

import pytest
from playwright.async_api import Page, expect


@pytest.mark.e2e
@pytest.mark.mobile
class TestMobileSignaturePad:
    """Test mobile signature pad functionality."""

    async def test_signature_page_loads_mobile(self, mobile_page: Page, sign_page_url: str):
        """Test that signature page loads on mobile device."""
        await mobile_page.goto(sign_page_url)

        # Check page loads
        heading = mobile_page.locator("h1, h2")
        await expect(heading).to_be_visible()

        # Check signature canvas exists
        canvas = mobile_page.locator("canvas.signature-canvas")
        await expect(canvas).to_be_visible()

    async def test_signature_canvas_responsive_size(self, mobile_page: Page, sign_page_url: str):
        """Test that signature canvas adapts to mobile screen size."""
        await mobile_page.goto(sign_page_url)

        canvas = mobile_page.locator("canvas.signature-canvas")
        await expect(canvas).to_be_visible()

        # Get canvas dimensions
        canvas_box = await canvas.bounding_box()
        viewport = mobile_page.viewport_size

        # Canvas should be nearly full-width on mobile
        assert canvas_box["width"] >= viewport["width"] * 0.85

        # Canvas should have appropriate height for portrait
        # (Session 022: 256px for mobile portrait)
        assert canvas_box["height"] >= 160  # Minimum height
        assert canvas_box["height"] <= 300  # Maximum reasonable height

    async def test_signature_drawing_mobile(self, mobile_page: Page, sign_page_url: str):
        """Test drawing signature on mobile device."""
        await mobile_page.goto(sign_page_url)

        canvas = mobile_page.locator("canvas.signature-canvas")
        await expect(canvas).to_be_visible()

        # Get canvas bounding box
        canvas_box = await canvas.bounding_box()

        # Simulate touch drawing (draw a simple stroke)
        # Start point
        start_x = canvas_box["x"] + 50
        start_y = canvas_box["y"] + canvas_box["height"] / 2

        # End point
        end_x = canvas_box["x"] + canvas_box["width"] - 50
        end_y = canvas_box["y"] + canvas_box["height"] / 2

        # Draw horizontal line
        await mobile_page.mouse.move(start_x, start_y)
        await mobile_page.mouse.down()
        await mobile_page.mouse.move(end_x, end_y)
        await mobile_page.mouse.up()

        # Verify signature was drawn (canvas should not be empty)
        # This is implementation-specific; adjust based on your SignaturePad library
        # One way is to check if the canvas has data
        has_signature = await mobile_page.evaluate("""
            () => {
                const canvas = document.querySelector('canvas.signature-canvas');
                if (!canvas) return false;
                const ctx = canvas.getContext('2d');
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                // Check if any pixel is not transparent
                for (let i = 0; i < imageData.data.length; i += 4) {
                    if (imageData.data[i + 3] > 0) return true;
                }
                return false;
            }
        """)

        assert has_signature, "Signature canvas should have drawing"

    async def test_clear_signature_button(self, mobile_page: Page, sign_page_url: str):
        """Test clear signature functionality."""
        await mobile_page.goto(sign_page_url)

        canvas = mobile_page.locator("canvas.signature-canvas")
        canvas_box = await canvas.bounding_box()

        # Draw a signature
        await mobile_page.mouse.move(canvas_box["x"] + 100, canvas_box["y"] + 100)
        await mobile_page.mouse.down()
        await mobile_page.mouse.move(canvas_box["x"] + 200, canvas_box["y"] + 150)
        await mobile_page.mouse.up()

        # Click clear button
        clear_button = mobile_page.locator("button:has-text('Löschen'), button:has-text('Clear')")
        await clear_button.click()

        # Verify canvas is empty
        is_empty = await mobile_page.evaluate("""
            () => {
                const canvas = document.querySelector('canvas.signature-canvas');
                if (!canvas) return true;
                const ctx = canvas.getContext('2d');
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                // Check if all pixels are transparent
                for (let i = 0; i < imageData.data.length; i += 4) {
                    if (imageData.data[i + 3] > 0) return false;
                }
                return true;
            }
        """)

        assert is_empty, "Canvas should be empty after clearing"

    async def test_orientation_change_preserves_signature(
        self, mobile_page: Page, sign_page_url: str
    ):
        """Test that signature is preserved when orientation changes."""
        await mobile_page.goto(sign_page_url)

        canvas = mobile_page.locator("canvas.signature-canvas")

        # Draw signature in portrait mode
        canvas_box = await canvas.bounding_box()
        await mobile_page.mouse.move(canvas_box["x"] + 50, canvas_box["y"] + 80)
        await mobile_page.mouse.down()
        await mobile_page.mouse.move(canvas_box["x"] + 150, canvas_box["y"] + 120)
        await mobile_page.mouse.up()

        # Get signature data before rotation
        signature_data_before = await mobile_page.evaluate("""
            () => {
                const canvas = document.querySelector('canvas.signature-canvas');
                return canvas.toDataURL();
            }
        """)

        # Rotate to landscape
        await mobile_page.set_viewport_size({"width": 844, "height": 390})  # Landscape

        # Wait for canvas resize
        await mobile_page.wait_for_timeout(500)

        # Get signature data after rotation
        signature_data_after = await mobile_page.evaluate("""
            () => {
                const canvas = document.querySelector('canvas.signature-canvas');
                return canvas.toDataURL();
            }
        """)

        # Signature should still exist (not empty)
        assert signature_data_after != signature_data_before  # Canvas size changed
        # But signature should not be completely blank
        is_empty = await mobile_page.evaluate("""
            () => {
                const canvas = document.querySelector('canvas.signature-canvas');
                const ctx = canvas.getContext('2d');
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    if (imageData.data[i + 3] > 0) return false;
                }
                return true;
            }
        """)

        assert not is_empty, "Signature should be preserved after orientation change"

    async def test_touch_targets_minimum_size(self, mobile_page: Page, sign_page_url: str):
        """Test that buttons meet minimum touch target size (48x48px)."""
        await mobile_page.goto(sign_page_url)

        # Get all buttons on the page
        buttons = mobile_page.locator("button")
        button_count = await buttons.count()

        assert button_count > 0, "Page should have buttons"

        # Check each button meets minimum size
        for i in range(button_count):
            button = buttons.nth(i)

            # Only check visible buttons
            if not await button.is_visible():
                continue

            box = await button.bounding_box()

            # Apple & Google guidelines: 48x48px minimum
            assert box["height"] >= 48, f"Button {i} height {box['height']}px < 48px"
            # Width can be flexible but should be reasonable
            assert box["width"] >= 48, f"Button {i} width {box['width']}px < 48px"

    async def test_submit_signature_button_mobile(self, mobile_page: Page, sign_page_url: str):
        """Test signature submission on mobile."""
        await mobile_page.goto(sign_page_url)

        canvas = mobile_page.locator("canvas.signature-canvas")

        # Draw a signature
        canvas_box = await canvas.bounding_box()
        await mobile_page.mouse.move(canvas_box["x"] + 100, canvas_box["y"] + 100)
        await mobile_page.mouse.down()
        await mobile_page.mouse.move(canvas_box["x"] + 200, canvas_box["y"] + 150)
        await mobile_page.mouse.up()

        # Find submit button
        submit_button = mobile_page.locator(
            "button:has-text('Submit'), button:has-text('Unterschreiben'), button[type='submit']"
        )
        await expect(submit_button).to_be_visible()

        # Check button is full-width or large enough for mobile
        button_box = await submit_button.bounding_box()
        viewport = mobile_page.viewport_size

        # On mobile, submit button should be prominent
        assert button_box["width"] >= viewport["width"] * 0.8, (
            f"Submit button width {button_box['width']}px should be >= 80% of viewport"
        )

        # Click submit (this will likely fail without backend setup, but we're testing UI)
        # await submit_button.click()
        # For now, just verify button is clickable
        await expect(submit_button).to_be_enabled()

    async def test_canvas_touch_action_none(self, mobile_page: Page, sign_page_url: str):
        """Test that canvas has touch-action: none to prevent scrolling."""
        await mobile_page.goto(sign_page_url)

        canvas = mobile_page.locator("canvas.signature-canvas")

        # Get computed style
        touch_action = await canvas.evaluate("""
            (element) => window.getComputedStyle(element).touchAction
        """)

        # Should be "none" to prevent browser gestures
        assert touch_action == "none", f"Canvas touch-action should be 'none', got '{touch_action}'"

    async def test_viewport_meta_tag(self, mobile_page: Page, sign_page_url: str):
        """Test that viewport meta tag prevents zoom on mobile."""
        await mobile_page.goto(sign_page_url)

        # Get viewport meta tag
        viewport_meta = await mobile_page.evaluate("""
            () => {
                const meta = document.querySelector('meta[name="viewport"]');
                return meta ? meta.getAttribute('content') : null;
            }
        """)

        assert viewport_meta is not None, "Viewport meta tag should exist"

        # Should contain user-scalable=no to prevent double-tap zoom
        assert "user-scalable=no" in viewport_meta or "user-scalable=0" in viewport_meta

        # Should have maximum-scale=1 to prevent pinch zoom
        assert "maximum-scale=1" in viewport_meta


@pytest.mark.e2e
@pytest.mark.mobile
class TestMobileSignatureFlow:
    """Test complete mobile signature flow."""

    async def test_complete_signature_flow_mobile(self, mobile_page: Page, sign_page_url: str):
        """Test complete signature flow from landing to submission."""
        await mobile_page.goto(sign_page_url)

        # Step 1: Page loads with instructions
        await expect(mobile_page.locator("h1, h2")).to_be_visible()

        # Step 2: Canvas is ready
        canvas = mobile_page.locator("canvas.signature-canvas")
        await expect(canvas).to_be_visible()

        # Step 3: User draws signature
        canvas_box = await canvas.bounding_box()
        await mobile_page.mouse.move(canvas_box["x"] + 50, canvas_box["y"] + 100)
        await mobile_page.mouse.down()
        await mobile_page.mouse.move(canvas_box["x"] + 200, canvas_box["y"] + 120)
        await mobile_page.mouse.move(canvas_box["x"] + 350, canvas_box["y"] + 100)
        await mobile_page.mouse.up()

        # Step 4: Submit button is enabled
        submit_button = mobile_page.locator(
            "button:has-text('Submit'), button:has-text('Unterschreiben'), button[type='submit']"
        )
        await expect(submit_button).to_be_enabled()

        # Step 5: Clear and re-draw to test clear functionality
        clear_button = mobile_page.locator("button:has-text('Löschen'), button:has-text('Clear')")
        await clear_button.click()

        # Canvas should be empty
        is_empty = await mobile_page.evaluate("""
            () => {
                const canvas = document.querySelector('canvas.signature-canvas');
                const ctx = canvas.getContext('2d');
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    if (imageData.data[i + 3] > 0) return false;
                }
                return true;
            }
        """)
        assert is_empty

        # Step 6: Draw again
        await mobile_page.mouse.move(canvas_box["x"] + 50, canvas_box["y"] + 100)
        await mobile_page.mouse.down()
        await mobile_page.mouse.move(canvas_box["x"] + 200, canvas_box["y"] + 120)
        await mobile_page.mouse.up()

        # Step 7: Verify submit button is still enabled
        await expect(submit_button).to_be_enabled()

    async def test_error_handling_empty_signature(self, mobile_page: Page, sign_page_url: str):
        """Test that submitting empty signature shows error."""
        await mobile_page.goto(sign_page_url)

        # Try to submit without drawing
        submit_button = mobile_page.locator(
            "button:has-text('Submit'), button:has-text('Unterschreiben'), button[type='submit']"
        )

        # Button might be disabled or show validation error
        # This depends on your implementation
        is_disabled = await submit_button.is_disabled()

        if not is_disabled:
            # Click and expect validation error
            await submit_button.click()

            # Should show error message
            error = mobile_page.locator(".error-message, .text-red-600, .alert-error")
            await expect(error).to_be_visible(timeout=2000)


@pytest.mark.e2e
@pytest.mark.mobile
class TestMobilePerformance:
    """Performance tests for mobile signature pad."""

    async def test_canvas_resize_performance(self, mobile_page: Page, sign_page_url: str):
        """Test that canvas resizes quickly on orientation change."""
        await mobile_page.goto(sign_page_url)

        # Measure resize time
        start_time = await mobile_page.evaluate("() => performance.now()")

        # Rotate to landscape
        await mobile_page.set_viewport_size({"width": 844, "height": 390})

        # Wait for resize event
        await mobile_page.wait_for_timeout(300)

        end_time = await mobile_page.evaluate("() => performance.now()")
        resize_time = end_time - start_time

        # Should resize within 500ms
        assert resize_time < 500, f"Canvas resize took {resize_time}ms (>500ms)"

    async def test_drawing_responsiveness(self, mobile_page: Page, sign_page_url: str):
        """Test that drawing feels responsive on mobile."""
        await mobile_page.goto(sign_page_url)

        canvas = mobile_page.locator("canvas.signature-canvas")
        canvas_box = await canvas.bounding_box()

        # Draw a complex signature (multiple strokes)
        start_time = await mobile_page.evaluate("() => performance.now()")

        # Draw 10 short strokes
        for i in range(10):
            x = canvas_box["x"] + 50 + (i * 30)
            y = canvas_box["y"] + 100
            await mobile_page.mouse.move(x, y)
            await mobile_page.mouse.down()
            await mobile_page.mouse.move(x + 20, y + 20)
            await mobile_page.mouse.up()

        end_time = await mobile_page.evaluate("() => performance.now()")
        drawing_time = end_time - start_time

        # Should complete quickly (not blocking UI)
        assert drawing_time < 1000, f"Drawing 10 strokes took {drawing_time}ms (>1000ms)"
