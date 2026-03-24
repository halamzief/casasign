"""Pytest configuration and fixtures for FES signature service tests."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "e2e: End-to-end tests with Playwright")
    config.addinivalue_line("markers", "mobile: Mobile-specific tests")
    config.addinivalue_line("markers", "admin: Admin UI tests")
    config.addinivalue_line("markers", "api: API-level tests (no browser)")


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Playwright Fixtures
# ============================================================================


@pytest.fixture(scope="session")
async def playwright() -> AsyncGenerator[Playwright, None]:
    """Launch Playwright for the session."""
    async with async_playwright() as playwright_instance:
        yield playwright_instance


@pytest.fixture(scope="session")
async def browser(playwright: Playwright) -> AsyncGenerator[Browser, None]:
    """Launch browser for the session."""
    browser = await playwright.chromium.launch(
        headless=True,  # Run headless for CI/CD
        args=[
            "--disable-blink-features=AutomationControlled",  # Avoid detection
        ],
    )
    yield browser
    await browser.close()


@pytest.fixture
async def context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Create new browser context for each test."""
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    yield context
    await context.close()


@pytest.fixture
async def page(context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create new page for each test."""
    page = await context.new_page()
    yield page
    await page.close()


# ============================================================================
# Mobile Device Fixtures
# ============================================================================


@pytest.fixture
async def mobile_context(
    browser: Browser, playwright: Playwright
) -> AsyncGenerator[BrowserContext, None]:
    """Create mobile browser context (iPhone 14 Pro)."""
    device = playwright.devices["iPhone 14 Pro"]
    context = await browser.new_context(**device)
    yield context
    await context.close()


@pytest.fixture
async def mobile_page(mobile_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create mobile page for testing."""
    page = await mobile_context.new_page()
    yield page
    await page.close()


# ============================================================================
# Application URL Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for FES signature service."""
    return "http://localhost:5175"


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """API base URL for FES signature service."""
    return "http://localhost:9001"


@pytest.fixture
def admin_templates_url(base_url: str) -> str:
    """Admin templates page URL."""
    return f"{base_url}/admin/templates"


@pytest.fixture
def sign_page_url(base_url: str) -> str:
    """Signing page URL (with test token)."""
    return f"{base_url}/sign/test-token"


# ============================================================================
# Helper Fixtures
# ============================================================================


@pytest.fixture
async def screenshot_on_failure(page: Page, request):
    """Take screenshot on test failure."""
    yield
    if request.node.rep_call.failed:
        screenshot_path = f"test-results/{request.node.name}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n📸 Screenshot saved: {screenshot_path}")
