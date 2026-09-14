"""Playwright Browser Automation Tools for YANA Developer & Desktop Assistant.

Implements 12 browser tools:
1.  browser.open
2.  browser.navigate
3.  browser.back
4.  browser.forward
5.  browser.refresh
6.  browser.read
7.  browser.click
8.  browser.type
9.  browser.select
10. browser.scroll
11. browser.download
12. browser.get_page_info

Adheres to Automation Priority Hierarchy:
DOM & Accessibility Tree (role, name, placeholder) -> Semantic Selectors -> Coordinates.
"""

from pathlib import Path
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.errors import ToolError, ValidationError
from app.logger import logger
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool
from app.tools.browser.security import (
    sanitize_untrusted_web_content,
    validate_safe_url,
)
from app.tools.browser.session import BrowserSessionManager, get_browser_session


class BaseBrowserTool(BaseTool):
    """Common base for Playwright browser tools."""

    category = "browser"

    def __init__(self, session_manager: BrowserSessionManager | None = None) -> None:
        self.session_manager = session_manager or get_browser_session()


class BrowserOpenTool(BaseBrowserTool):
    """Opens a browser session or new tab, optionally navigating to an initial URL."""

    name = "browser.open"
    description = (
        "Opens or initializes a browser session or tab, optionally navigating to an initial URL."
    )
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Optional initial URL to navigate to upon opening",
            },
            "headless": {
                "type": "boolean",
                "description": "Whether to run in headless mode (default True)",
                "default": True,
            },
            "new_window": {
                "type": "boolean",
                "description": "Whether to open in a new tab/window",
                "default": False,
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        url = arguments.get("url")
        if url:
            validate_safe_url(url)

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        url = arguments.get("url")
        headless = arguments.get("headless", True)
        new_window = arguments.get("new_window", False)

        try:
            await self.session_manager.get_or_create_context(headless=headless)
            if new_window:
                page = await self.session_manager.new_page(url=url)
            else:
                page = await self.session_manager.get_active_page()
                if url:
                    safe_url = validate_safe_url(url)
                    await page.goto(safe_url, wait_until="domcontentloaded", timeout=30000)

            title = await page.title()
            return {
                "status": "opened",
                "url": page.url,
                "title": title,
                "headless": headless,
            }
        except Exception as e:
            logger.error("Error in browser.open: %s", e)
            raise ToolError(f"Failed to open browser: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "opened"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.open",
            verified=verified,
            notes=f"Browser opened at '{output.get('url', '')}'."
            if verified
            else "Browser open verification failed.",
        )


class BrowserNavigateTool(BaseBrowserTool):
    """Navigates the active browser page to a target URL."""

    name = "browser.navigate"
    description = "Navigates the current browser tab to a specified URL."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The destination URL to navigate to",
            },
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                "default": "domcontentloaded",
                "description": "When to consider navigation succeeded",
            },
            "timeout_seconds": {
                "type": "number",
                "default": 30.0,
                "description": "Navigation timeout in seconds",
            },
        },
        "required": ["url"],
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        validate_safe_url(arguments["url"])

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raw_url = arguments["url"]
        safe_url = validate_safe_url(raw_url)
        wait_until = arguments.get("wait_until", "domcontentloaded")
        timeout_ms = int(arguments.get("timeout_seconds", 30.0) * 1000)

        try:
            page = await self.session_manager.get_active_page()
            response = await page.goto(safe_url, wait_until=wait_until, timeout=timeout_ms)
            status_code = response.status if response else 200
            title = await page.title()

            return {
                "status": "navigated",
                "url": page.url,
                "title": title,
                "status_code": status_code,
            }
        except PlaywrightTimeoutError as e:
            raise ToolError(f"Navigation to '{safe_url}' timed out: {e}") from e
        except Exception as e:
            logger.error("Navigation failed: %s", e)
            raise ToolError(f"Failed to navigate to '{safe_url}': {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "navigated"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.navigate",
            verified=verified,
            notes=f"Navigated to '{output.get('url')}' (status: {output.get('status_code')})."
            if verified
            else "Navigation verification failed.",
        )


class BrowserBackTool(BaseBrowserTool):
    """Navigates back in browser history."""

    name = "browser.back"
    description = "Navigates back to the previous page in browser history."
    risk_level = RiskLevel.LOW
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            page = await self.session_manager.get_active_page()
            await page.go_back(wait_until="domcontentloaded", timeout=15000)
            return {
                "status": "navigated_back",
                "url": page.url,
                "title": await page.title(),
            }
        except Exception as e:
            raise ToolError(f"Failed to navigate back: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "navigated_back"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.back",
            verified=verified,
            notes="Back navigation successful." if verified else "Back navigation failed.",
        )


class BrowserForwardTool(BaseBrowserTool):
    """Navigates forward in browser history."""

    name = "browser.forward"
    description = "Navigates forward to the next page in browser history."
    risk_level = RiskLevel.LOW
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            page = await self.session_manager.get_active_page()
            await page.go_forward(wait_until="domcontentloaded", timeout=15000)
            return {
                "status": "navigated_forward",
                "url": page.url,
                "title": await page.title(),
            }
        except Exception as e:
            raise ToolError(f"Failed to navigate forward: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "navigated_forward"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.forward",
            verified=verified,
            notes="Forward navigation successful." if verified else "Forward navigation failed.",
        )


class BrowserRefreshTool(BaseBrowserTool):
    """Reloads the current page."""

    name = "browser.refresh"
    description = "Reloads the current page in the active browser tab."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle"],
                "default": "domcontentloaded",
            },
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        wait_until = arguments.get("wait_until", "domcontentloaded")
        try:
            page = await self.session_manager.get_active_page()
            await page.reload(wait_until=wait_until, timeout=30000)
            return {
                "status": "refreshed",
                "url": page.url,
                "title": await page.title(),
            }
        except Exception as e:
            raise ToolError(f"Failed to refresh page: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "refreshed"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.refresh",
            verified=verified,
            notes="Page refresh successful." if verified else "Page refresh failed.",
        )


class BrowserReadTool(BaseBrowserTool):
    """Reads textual and semantic content from the webpage with untrusted boundary isolation."""

    name = "browser.read"
    description = (
        "Safely extracts page text or element contents, wrapping untrusted web content "
        "in structural delimiters and defanging prompt injection phrases."
    )
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": (
                    "Optional CSS selector or accessibility locator to read specifically"
                ),
            },
            "max_bytes": {
                "type": "integer",
                "default": 65536,
                "description": "Maximum bytes to return (default 64KB)",
            },
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        selector = arguments.get("selector")
        max_bytes = int(arguments.get("max_bytes", 65536))

        try:
            page = await self.session_manager.get_active_page()
            url = page.url
            title = await page.title()

            if selector:
                locator = page.locator(selector).first
                raw_text = await locator.inner_text(timeout=5000)
            else:
                # Extract clean visible body text
                raw_text = await page.inner_text("body", timeout=5000)

            # Isolate and defang untrusted external web content
            sanitized_content = sanitize_untrusted_web_content(
                raw_text, source_url=url, max_bytes=max_bytes
            )

            return {
                "status": "read",
                "url": url,
                "title": title,
                "content": sanitized_content,
                "length_bytes": len(sanitized_content.encode("utf-8")),
            }
        except Exception as e:
            logger.error("Error reading webpage: %s", e)
            raise ToolError(f"Failed to read webpage content: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and "content" in output
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.read",
            verified=verified,
            notes=f"Read {output.get('length_bytes', 0)} bytes of sanitized content."
            if verified
            else "Webpage read verification failed.",
        )


class BrowserClickTool(BaseBrowserTool):
    """Clicks an element using Automation Priority: Accessibility tree -> Selectors -> Coords."""

    name = "browser.click"
    description = (
        "Clicks an interactive element on the page prioritizing accessible roles and names "
        "(getByRole, getByText) over selectors and coordinate fallbacks."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "description": "Accessible role (e.g. 'button', 'link', 'checkbox', 'tab')",
            },
            "name": {
                "type": "string",
                "description": "Accessible name, label, or visible text of the element",
            },
            "selector": {
                "type": "string",
                "description": "CSS or XPath selector fallback",
            },
            "coordinates": {
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
                "description": "Last-resort coordinate fallback",
            },
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "default": "left",
            },
            "click_count": {
                "type": "integer",
                "default": 1,
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        has_accessible = bool(arguments.get("role") or arguments.get("name"))
        has_selector = bool(arguments.get("selector"))
        has_coords = bool(arguments.get("coordinates"))
        if not (has_accessible or has_selector or has_coords):
            raise ValidationError(
                "Must provide accessible target ('role' or 'name'), 'selector', or 'coordinates'."
            )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        role = arguments.get("role")
        name = arguments.get("name")
        selector = arguments.get("selector")
        coords = arguments.get("coordinates")
        btn = arguments.get("button", "left")
        click_count = int(arguments.get("click_count", 1))

        page = await self.session_manager.get_active_page()

        try:
            # 1. Accessibility Tree & Semantic Resolution (Top Priority)
            if role and name:
                locator = page.get_by_role(role, name=name).first
                await locator.click(button=btn, click_count=click_count, timeout=5000)
                target_desc = f"role='{role}', name='{name}'"
            elif role:
                locator = page.get_by_role(role).first
                await locator.click(button=btn, click_count=click_count, timeout=5000)
                target_desc = f"role='{role}'"
            elif name:
                locator = page.get_by_text(name).first
                await locator.click(button=btn, click_count=click_count, timeout=5000)
                target_desc = f"text='{name}'"
            # 2. Selector Resolution
            elif selector:
                locator = page.locator(selector).first
                await locator.click(button=btn, click_count=click_count, timeout=5000)
                target_desc = f"selector='{selector}'"
            # 3. Coordinate Fallback
            elif coords:
                x = coords.get("x", 0)
                y = coords.get("y", 0)
                await page.mouse.click(x, y, button=btn, click_count=click_count)
                target_desc = f"coordinates=({x}, {y})"
            else:
                raise ValidationError("No valid target specified for click.")

            return {
                "status": "clicked",
                "target": target_desc,
                "url": page.url,
            }
        except Exception as e:
            logger.error("Click error: %s", e)
            raise ToolError(f"Failed to click target: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "clicked"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.click",
            verified=verified,
            notes=f"Clicked {output.get('target', '')} successfully."
            if verified
            else "Click verification failed.",
        )


class BrowserTypeTool(BaseBrowserTool):
    """Types text into an editable element using semantic locators."""

    name = "browser.type"
    description = (
        "Types text into an input or editable field, prioritizing accessible labels "
        "and placeholders over selectors."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text content to type into the field",
            },
            "role": {
                "type": "string",
                "description": "Accessible role (e.g. 'textbox', 'searchbox')",
            },
            "name": {
                "type": "string",
                "description": "Accessible label, placeholder, or name of the field",
            },
            "selector": {
                "type": "string",
                "description": "Optional CSS selector for the input element",
            },
            "clear": {
                "type": "boolean",
                "default": False,
                "description": "Whether to clear existing text before typing",
            },
            "press_enter": {
                "type": "boolean",
                "default": False,
                "description": "Whether to press Enter after typing (e.g. to submit search)",
            },
        },
        "required": ["text"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        text = arguments["text"]
        role = arguments.get("role")
        name = arguments.get("name")
        selector = arguments.get("selector")
        clear = bool(arguments.get("clear", False))
        press_enter = bool(arguments.get("press_enter", False))

        page = await self.session_manager.get_active_page()

        try:
            # Locate target element
            locator = None
            target_desc = "active_element"

            if role and name:
                locator = page.get_by_role(role, name=name).first
                target_desc = f"role='{role}', name='{name}'"
            elif name:
                # Try placeholder or label first
                try:
                    locator = page.get_by_placeholder(name).first
                    target_desc = f"placeholder='{name}'"
                except Exception:
                    locator = page.get_by_label(name).first
                    target_desc = f"label='{name}'"
            elif role:
                locator = page.get_by_role(role).first
                target_desc = f"role='{role}'"
            elif selector:
                locator = page.locator(selector).first
                target_desc = f"selector='{selector}'"

            if locator is not None:
                if clear:
                    await locator.fill("")
                await locator.fill(text, timeout=5000)
                if press_enter:
                    await locator.press("Enter")
            else:
                # Direct keyboard type into focused field
                await page.keyboard.type(text)
                if press_enter:
                    await page.keyboard.press("Enter")

            return {
                "status": "typed",
                "target": target_desc,
                "text_length": len(text),
                "press_enter": press_enter,
            }
        except Exception as e:
            logger.error("Typing error: %s", e)
            raise ToolError(f"Failed to type into target: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "typed"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.type",
            verified=verified,
            notes=f"Typed {output.get('text_length', 0)} characters into {output.get('target')}."
            if verified
            else "Typing verification failed.",
        )


class BrowserSelectTool(BaseBrowserTool):
    """Selects option(s) in a dropdown or choice control."""

    name = "browser.select"
    description = "Selects one or more options in a dropdown or select element."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "value": {
                "type": "string",
                "description": "Value or label of the option to select",
            },
            "selector": {
                "type": "string",
                "description": "Optional CSS selector for the select element",
            },
            "role": {
                "type": "string",
                "default": "combobox",
            },
            "name": {
                "type": "string",
                "description": "Accessible name or label of the select control",
            },
        },
        "required": ["value"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        val = arguments["value"]
        selector = arguments.get("selector")
        name = arguments.get("name")
        role = arguments.get("role", "combobox")

        page = await self.session_manager.get_active_page()

        try:
            if selector:
                locator = page.locator(selector).first
            elif name:
                locator = page.get_by_role(role, name=name).first
            else:
                locator = page.get_by_role(role).first

            selected = await locator.select_option(value=val, timeout=5000)
            return {
                "status": "selected",
                "value": val,
                "selected_values": selected,
            }
        except Exception as e:
            logger.error("Select error: %s", e)
            raise ToolError(f"Failed to select option '{val}': {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "selected"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.select",
            verified=verified,
            notes=f"Selected option '{output.get('value')}' successfully."
            if verified
            else "Selection verification failed.",
        )


class BrowserScrollTool(BaseBrowserTool):
    """Scrolls the active webpage or container element."""

    name = "browser.scroll"
    description = "Scrolls the webpage by direction ('down', 'up', 'top', 'bottom') or pixels."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["down", "up", "top", "bottom"],
                "default": "down",
            },
            "pixels": {
                "type": "integer",
                "default": 500,
            },
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        direction = arguments.get("direction", "down")
        pixels = int(arguments.get("pixels", 500))

        page = await self.session_manager.get_active_page()

        try:
            if direction == "down":
                await page.mouse.wheel(0, pixels)
            elif direction == "up":
                await page.mouse.wheel(0, -pixels)
            elif direction == "top":
                await page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            return {
                "status": "scrolled",
                "direction": direction,
                "pixels": pixels,
            }
        except Exception as e:
            raise ToolError(f"Failed to scroll: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "scrolled"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.scroll",
            verified=verified,
            notes=f"Scrolled {output.get('direction', '')} successfully."
            if verified
            else "Scroll verification failed.",
        )


class BrowserDownloadTool(BaseBrowserTool):
    """Downloads a file to the sandbox directory without automatic execution."""

    name = "browser.download"
    description = (
        "Initiates and captures a file download into a sandboxed directory. "
        "Strictly forbids automatic program execution."
    )
    risk_level = RiskLevel.HIGH
    input_schema = {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "Selector or link that triggers the download when clicked",
            },
            "url": {
                "type": "string",
                "description": "Optional direct URL to trigger download for",
            },
            "filename": {
                "type": "string",
                "description": "Optional suggested filename",
            },
            "timeout_seconds": {
                "type": "number",
                "default": 30.0,
            },
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        selector = arguments.get("selector")
        url = arguments.get("url")
        custom_name = arguments.get("filename")
        timeout_ms = int(arguments.get("timeout_seconds", 30.0) * 1000)

        page = await self.session_manager.get_active_page()
        sandbox = self.session_manager.download_sandbox

        try:
            if url:
                validate_safe_url(url)

            # Wait for download event
            async with page.expect_download(timeout=timeout_ms) as download_info:
                if selector:
                    await page.locator(selector).first.click()
                elif url:
                    await page.goto(url)
                else:
                    raise ValidationError("Must provide 'selector' or 'url' to trigger download.")

            download = await download_info.value
            suggested_name = custom_name or download.suggested_filename
            dest_path = sandbox.get_destination_path(suggested_name)

            # Save file into sandbox
            await download.save_as(str(dest_path))

            # Strictly enforce non-executable invariant
            sandbox.mark_non_executable(dest_path)

            file_size = dest_path.stat().st_size if dest_path.exists() else 0

            return {
                "status": "downloaded",
                "filename": dest_path.name,
                "saved_path": str(dest_path),
                "size_bytes": file_size,
                "sandbox_dir": str(sandbox.sandbox_dir),
                "executable_forbidden": True,
                "auto_execution_blocked": True,
            }
        except Exception as e:
            logger.error("Download error: %s", e)
            raise ToolError(f"Failed to download file: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        saved = output.get("saved_path") if isinstance(output, dict) else None
        verified = bool(saved and Path(saved).is_file())
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.download",
            verified=verified,
            notes=f"File saved to sandbox at '{saved}' (executable strictly forbidden)."
            if verified
            else "Download verification failed.",
        )


class BrowserGetPageInfoTool(BaseBrowserTool):
    """Inspects active page metadata, URL, title, dimensions, and accessible controls."""

    name = "browser.get_page_info"
    description = (
        "Retrieves page title, URL, dimensions, and a structural summary of accessible "
        "interactive controls (buttons, links, inputs)."
    )
    risk_level = RiskLevel.LOW
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            page = await self.session_manager.get_active_page()
            url = page.url
            title = await page.title()
            viewport = page.viewport_size or {"width": 1280, "height": 800}

            # Query visible interactive elements
            interactive_summary = await page.evaluate(
                """() => {
                    const elements = [];
                    const items = document.querySelectorAll(
                        'button, a[href], input, select, textarea, [role="button"], [role="link"]'
                    );
                    for (const el of Array.from(items).slice(0, 40)) {
                        const tag = el.tagName.toLowerCase();
                        const aria = el.getAttribute('aria-label') || '';
                        const ph = el.getAttribute('placeholder') || '';
                        const text = (el.innerText || aria || ph || el.value || '').trim();
                        const role = el.getAttribute('role') || tag;
                        if (text) {
                            elements.push({ tag, role, text: text.slice(0, 50) });
                        }
                    }
                    return elements;
                }"""
            )

            return {
                "status": "inspected",
                "url": url,
                "title": title,
                "viewport": viewport,
                "interactive_elements": interactive_summary,
            }
        except Exception as e:
            raise ToolError(f"Failed to retrieve page info: {e}") from e

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "inspected"
        return VerificationResult(
            task_id="browser",
            tool_call_id="browser.get_page_info",
            verified=verified,
            notes=f"Page info retrieved: '{output.get('title')}' ({output.get('url')})."
            if verified
            else "Page info verification failed.",
        )
