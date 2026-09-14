"""Asynchronous Playwright Browser Session Management for YANA AI Agent.

Manages lifecycle of Playwright driver, Chromium browser instance, browser context,
active tabs/pages, and sandboxed download paths.
"""

from pathlib import Path

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from app.logger import logger
from app.tools.browser.security import DownloadSandboxManager


class BrowserSessionManager:
    """Manages the shared asynchronous Playwright browser session."""

    def __init__(self, sandbox_dir: Path | None = None) -> None:
        self.download_sandbox = DownloadSandboxManager(sandbox_dir)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._pages: list[Page] = []
        self._active_page_index: int = 0
        self._default_headless: bool = True

    @property
    def is_running(self) -> bool:
        """Check whether the browser session is currently active."""
        return self._browser is not None and self._browser.is_connected()

    async def get_or_create_context(self, headless: bool | None = None) -> BrowserContext:
        """Initialize or retrieve the active Playwright browser context."""
        use_headless = self._default_headless if headless is None else headless

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None or not self._browser.is_connected():
            logger.info("Launching Playwright Chromium (headless=%s)", use_headless)
            self._browser = await self._playwright.chromium.launch(
                headless=use_headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

        if self._context is None:
            self._context = await self._browser.new_context(
                accept_downloads=True,
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 YANA/0.7.0"
                ),
            )
            # Route page events
            self._context.on("page", self._on_new_page)

        return self._context

    def _on_new_page(self, page: Page) -> None:
        """Track new pages/popups opened within the context."""
        if page not in self._pages:
            self._pages.append(page)
            self._active_page_index = len(self._pages) - 1

    async def get_active_page(self) -> Page:
        """Retrieve the currently focused page, creating one if none exist."""
        context = await self.get_or_create_context()

        # Clean up closed pages
        self._pages = [p for p in self._pages if not p.is_closed()]

        if not self._pages:
            page = await context.new_page()
            self._pages.append(page)
            self._active_page_index = 0
            return page

        if self._active_page_index >= len(self._pages):
            self._active_page_index = len(self._pages) - 1

        return self._pages[self._active_page_index]

    async def new_page(self, url: str | None = None) -> Page:
        """Open a new tab/page and set it as active."""
        context = await self.get_or_create_context()
        page = await context.new_page()
        if page not in self._pages:
            self._pages.append(page)
        self._active_page_index = len(self._pages) - 1

        if url:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        return page

    async def close_active_page(self) -> None:
        """Close the currently active page."""
        if self._pages:
            page = await self.get_active_page()
            await page.close()
            self._pages = [p for p in self._pages if not p.is_closed()]
            self._active_page_index = max(0, len(self._pages) - 1)

    async def close_session(self) -> None:
        """Completely close all browser contexts, browser processes, and Playwright driver."""
        logger.info("Closing Playwright browser session")
        self._pages.clear()
        self._active_page_index = 0

        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.warning("Error closing browser context: %s", e)
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning("Error closing browser: %s", e)
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning("Error stopping Playwright: %s", e)
            self._playwright = None


# Global singleton instance
browser_session = BrowserSessionManager()


def get_browser_session() -> BrowserSessionManager:
    """Access the global BrowserSessionManager instance."""
    return browser_session
