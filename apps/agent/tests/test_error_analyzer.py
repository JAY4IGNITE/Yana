"""Unit tests for Developer Error Analyzer Tool (developer.analyze_error).

Verifies root-cause diagnosis, error classification into standard categories,
entity extraction, actionable recovery proposals, and preservation of raw error logs.
"""

import pytest

from app.errors import ValidationError
from app.tools.developer.error_analyzer import DeveloperAnalyzeErrorTool


@pytest.mark.asyncio
async def test_error_analyzer_missing_dependency():
    tool = DeveloperAnalyzeErrorTool()
    err_text = "ModuleNotFoundError: No module named 'httpx'"

    tool.validate({"error_text": err_text})
    res = await tool.execute({"error_text": err_text, "runtime": "python"})

    assert res["category"] == "MISSING_DEPENDENCY"
    assert res["extracted_entities"]["missing_package"] == "httpx"
    assert "pip install httpx" in res["suggested_fix"]
    assert len(res["recovery_actions"]) > 0
    assert res["recovery_actions"][0]["arguments"]["command"] == "pip install httpx"
    assert res["raw_error"] == err_text

    verification = await tool.verify({"error_text": err_text}, res)
    assert verification.verified is True


@pytest.mark.asyncio
async def test_error_analyzer_port_in_use():
    tool = DeveloperAnalyzeErrorTool()
    err_text = (
        "ERROR:    [Errno 10048] error while attempting to bind on address "
        "('127.0.0.1', 8000): only one usage of each socket address is normally permitted"
    )

    res = await tool.execute({"error_text": err_text})

    assert res["category"] == "PORT_IN_USE"
    assert res["extracted_entities"]["port"] == 8000
    assert "8000" in res["suggested_fix"]
    assert any(
        "netstat" in a.get("arguments", {}).get("command", "") for a in res["recovery_actions"]
    )
    assert res["raw_error"] == err_text


@pytest.mark.asyncio
async def test_error_analyzer_syntax_error():
    tool = DeveloperAnalyzeErrorTool()
    err_text = (
        'File "app/main.py", line 42\n'
        "    def calculate(:\n"
        "                  ^\n"
        "SyntaxError: invalid syntax"
    )

    res = await tool.execute({"error_text": err_text})

    assert res["category"] == "SYNTAX_ERROR"
    assert res["extracted_entities"]["file"] == "app/main.py"
    assert res["extracted_entities"]["line"] == 42
    assert "invalid syntax" in res["extracted_entities"]["detail"]
    assert res["raw_error"] == err_text


@pytest.mark.asyncio
async def test_error_analyzer_command_not_found():
    tool = DeveloperAnalyzeErrorTool()
    err_text = (
        "'pnpm' is not recognized as an internal or external command, "
        "operable program or batch file."
    )

    res = await tool.execute({"error_text": err_text})

    assert res["category"] == "COMMAND_NOT_FOUND"
    assert res["extracted_entities"]["command"] == "pnpm"
    assert "pnpm" in res["suggested_fix"]
    assert res["raw_error"] == err_text


@pytest.mark.asyncio
async def test_error_analyzer_validation():
    tool = DeveloperAnalyzeErrorTool()

    with pytest.raises(ValidationError, match="required and must be non-empty"):
        tool.validate({"error_text": ""})
