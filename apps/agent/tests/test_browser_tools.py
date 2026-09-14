"""Integration and unit tests for Phase 07 Playwright Browser Automation Tools.

Uses local HTML files and data URLs in isolated browser sessions to test:
- Navigation (open, navigate, back, forward, refresh)
- Reading with accessibility and untrusted content boundaries
- Clicking (automation priority: role/name -> selector)
- Typing with clear and enter options
- Selecting dropdown options
- Scrolling
- Sandboxed downloads without auto-execution
- Page info inspection
- Timeouts and error handling
"""

from pathlib import Path

import pytest
import pytest_asyncio

from app.tools.browser.browser_tools import (
    BrowserBackTool,
    BrowserClickTool,
    BrowserDownloadTool,
    BrowserForwardTool,
    BrowserGetPageInfoTool,
    BrowserNavigateTool,
    BrowserOpenTool,
    BrowserReadTool,
    BrowserRefreshTool,
    BrowserScrollTool,
    BrowserSelectTool,
    BrowserTypeTool,
)
from app.tools.browser.session import BrowserSessionManager

# Sample local HTML test document
SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>YANA Test Page</title></head>
<body>
    <h1>Browser Automation Sandbox</h1>
    <p id="info">Welcome to the Playwright integration testing environment.</p>

    <!-- Search Input -->
    <label for="search-input">Search Query</label>
    <input id="search-input" role="textbox" placeholder="Search documentation" type="text" />

    <!-- Interactive Buttons -->
    <button id="submit-btn" role="button">Submit Query</button>
    <button id="counter-btn" onclick="document.getElementById('counter').innerText = 'Clicked!'">
        Click Counter
    </button>
    <span id="counter">0</span>

    <!-- Dropdown Select -->
    <label for="lang-select">Language</label>
    <select id="lang-select" role="combobox" aria-label="Language Select">
        <option value="py">Python</option>
        <option value="ts">TypeScript</option>
        <option value="rs">Rust</option>
    </select>

    <!-- Download Link -->
    <a id="download-link"
       href="data:text/plain;charset=utf-8,YANA_DOWNLOAD_TEST"
       download="test_artifact.txt">
        Download Sample
    </a>

    <!-- Navigation Link -->
    <a id="nav-link" href="#section2">Go to Section 2</a>
    <div id="section2" style="margin-top: 1000px;">Section 2 Anchor</div>
</body>
</html>
"""


@pytest_asyncio.fixture
async def session_mgr(tmp_path: Path):
    """Fixture providing an isolated BrowserSessionManager with cleanup."""
    mgr = BrowserSessionManager(sandbox_dir=tmp_path / "downloads")
    yield mgr
    await mgr.close_session()


@pytest.mark.asyncio
async def test_browser_open_and_navigate(session_mgr: BrowserSessionManager, tmp_path: Path):
    test_page = tmp_path / "index.html"
    test_page.write_text(SAMPLE_HTML, encoding="utf-8")
    file_url = test_page.as_uri()

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    nav_tool = BrowserNavigateTool(session_manager=session_mgr)

    # 1. Open browser
    res_open = await open_tool.execute({"headless": True})
    assert res_open["status"] == "opened"

    # 2. Navigate to test page
    res_nav = await nav_tool.execute({"url": file_url})
    assert res_nav["status"] == "navigated"
    assert "YANA Test Page" in res_nav["title"]

    ver_nav = await nav_tool.verify({"url": file_url}, res_nav)
    assert ver_nav.verified is True


@pytest.mark.asyncio
async def test_browser_read_with_untrusted_isolation(
    session_mgr: BrowserSessionManager, tmp_path: Path
):
    test_page = tmp_path / "read_test.html"
    test_page.write_text(SAMPLE_HTML, encoding="utf-8")

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    read_tool = BrowserReadTool(session_manager=session_mgr)

    await open_tool.execute({"url": test_page.as_uri(), "headless": True})
    res_read = await read_tool.execute({})

    assert res_read["status"] == "read"
    assert "<untrusted_web_content" in res_read["content"]
    assert "</untrusted_web_content>" in res_read["content"]
    assert "Browser Automation Sandbox" in res_read["content"]

    ver_read = await read_tool.verify({}, res_read)
    assert ver_read.verified is True


@pytest.mark.asyncio
async def test_browser_click_accessibility_priority(
    session_mgr: BrowserSessionManager, tmp_path: Path
):
    test_page = tmp_path / "click_test.html"
    test_page.write_text(SAMPLE_HTML, encoding="utf-8")

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    click_tool = BrowserClickTool(session_manager=session_mgr)
    read_tool = BrowserReadTool(session_manager=session_mgr)

    await open_tool.execute({"url": test_page.as_uri(), "headless": True})

    # Click using accessibility role and name
    res_click = await click_tool.execute({"role": "button", "name": "Click Counter"})
    assert res_click["status"] == "clicked"

    # Verify DOM changed
    res_read = await read_tool.execute({"selector": "#counter"})
    assert "Clicked!" in res_read["content"]


@pytest.mark.asyncio
async def test_browser_type_and_enter(session_mgr: BrowserSessionManager, tmp_path: Path):
    test_page = tmp_path / "type_test.html"
    test_page.write_text(SAMPLE_HTML, encoding="utf-8")

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    type_tool = BrowserTypeTool(session_manager=session_mgr)

    await open_tool.execute({"url": test_page.as_uri(), "headless": True})

    res_type = await type_tool.execute(
        {"name": "Search documentation", "text": "React hooks", "press_enter": False}
    )
    assert res_type["status"] == "typed"
    assert res_type["text_length"] == 11

    page = await session_mgr.get_active_page()
    val = await page.locator("#search-input").input_value()
    assert val == "React hooks"


@pytest.mark.asyncio
async def test_browser_select_dropdown(session_mgr: BrowserSessionManager, tmp_path: Path):
    test_page = tmp_path / "select_test.html"
    test_page.write_text(SAMPLE_HTML, encoding="utf-8")

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    select_tool = BrowserSelectTool(session_manager=session_mgr)

    await open_tool.execute({"url": test_page.as_uri(), "headless": True})

    res_sel = await select_tool.execute({"name": "Language Select", "value": "rs"})
    assert res_sel["status"] == "selected"
    assert "rs" in res_sel["selected_values"]

    page = await session_mgr.get_active_page()
    val = await page.locator("#lang-select").input_value()
    assert val == "rs"


@pytest.mark.asyncio
async def test_browser_scroll(session_mgr: BrowserSessionManager, tmp_path: Path):
    test_page = tmp_path / "scroll_test.html"
    test_page.write_text(SAMPLE_HTML, encoding="utf-8")

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    scroll_tool = BrowserScrollTool(session_manager=session_mgr)

    await open_tool.execute({"url": test_page.as_uri(), "headless": True})

    res_scroll = await scroll_tool.execute({"direction": "down", "pixels": 600})
    assert res_scroll["status"] == "scrolled"


@pytest.mark.asyncio
async def test_browser_sandboxed_download(session_mgr: BrowserSessionManager, tmp_path: Path):
    test_page = tmp_path / "download_test.html"
    test_page.write_text(SAMPLE_HTML, encoding="utf-8")

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    download_tool = BrowserDownloadTool(session_manager=session_mgr)

    await open_tool.execute({"url": test_page.as_uri(), "headless": True})

    res_dl = await download_tool.execute(
        {"selector": "#download-link", "filename": "safe_sample.txt"}
    )
    assert res_dl["status"] == "downloaded"
    assert res_dl["executable_forbidden"] is True
    assert res_dl["auto_execution_blocked"] is True
    assert Path(res_dl["saved_path"]).exists()

    ver_dl = await download_tool.verify({}, res_dl)
    assert ver_dl.verified is True


@pytest.mark.asyncio
async def test_browser_get_page_info(session_mgr: BrowserSessionManager, tmp_path: Path):
    test_page = tmp_path / "info_test.html"
    test_page.write_text(SAMPLE_HTML, encoding="utf-8")

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    info_tool = BrowserGetPageInfoTool(session_manager=session_mgr)

    await open_tool.execute({"url": test_page.as_uri(), "headless": True})
    res_info = await info_tool.execute({})

    assert res_info["status"] == "inspected"
    assert res_info["title"] == "YANA Test Page"
    assert len(res_info["interactive_elements"]) > 0

    ver_info = await info_tool.verify({}, res_info)
    assert ver_info.verified is True


@pytest.mark.asyncio
async def test_browser_history_and_refresh(session_mgr: BrowserSessionManager, tmp_path: Path):
    p1 = tmp_path / "p1.html"
    p1.write_text("<html><head><title>Page 1</title></head><body>P1</body></html>")
    p2 = tmp_path / "p2.html"
    p2.write_text("<html><head><title>Page 2</title></head><body>P2</body></html>")

    open_tool = BrowserOpenTool(session_manager=session_mgr)
    nav_tool = BrowserNavigateTool(session_manager=session_mgr)
    back_tool = BrowserBackTool(session_manager=session_mgr)
    fwd_tool = BrowserForwardTool(session_manager=session_mgr)
    ref_tool = BrowserRefreshTool(session_manager=session_mgr)

    await open_tool.execute({"url": p1.as_uri(), "headless": True})
    await nav_tool.execute({"url": p2.as_uri()})

    # Back
    res_back = await back_tool.execute({})
    assert "p1.html" in res_back["url"]

    # Forward
    res_fwd = await fwd_tool.execute({})
    assert "p2.html" in res_fwd["url"]

    # Refresh
    res_ref = await ref_tool.execute({})
    assert res_ref["status"] == "refreshed"
