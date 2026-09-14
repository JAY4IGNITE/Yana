"""Unit tests for Project Inspection Tool (project.inspect).

Tests manifest parsing (package.json, pyproject.toml, requirements.txt, Cargo.toml),
technology stack identification, scripts/dependencies extraction, and Git repository state.
"""

import json
from pathlib import Path

import pytest

from app.tools.project.project_inspector import ProjectInspectTool


@pytest.mark.asyncio
async def test_inspect_node_tauri_project(tmp_path: Path):
    # Setup mock package.json and tsconfig.json
    pkg_data = {
        "name": "desktop-client",
        "version": "1.2.0",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "test": "vitest",
        },
        "dependencies": {
            "@tauri-apps/api": "^2.0.0",
            "react": "^18.3.0",
            "react-dom": "^18.3.0",
        },
        "devDependencies": {
            "vite": "^5.0.0",
            "typescript": "^5.0.0",
        },
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    readme_text = "# Desktop Client\n\nYANA desktop frontend."
    (tmp_path / "README.md").write_text(readme_text, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("console.log('hi')", encoding="utf-8")

    tool = ProjectInspectTool(allowed_root=tmp_path)
    tool.validate({"path": str(tmp_path)})

    res = await tool.execute({"path": str(tmp_path)})
    assert "Node.js / JavaScript" in res["technologies"]
    assert "TypeScript" in res["technologies"]
    assert "Tauri" in res["technologies"]
    assert "React" in res["technologies"]
    assert "Vite" in res["technologies"]
    assert "package.json" in res["manifests_detected"]
    assert res["scripts"]["dev"] == "vite"
    assert "react" in res["dependencies"]["npm"]
    assert "Desktop Client" in (res["readme_summary"] or "")
    assert "src" in res["structure"]["top_level_directories"]

    verification = await tool.verify({"path": str(tmp_path)}, res)
    assert verification.verified is True


@pytest.mark.asyncio
async def test_inspect_python_project(tmp_path: Path):
    pyproject_data = (
        "[project]\n"
        'name = "backend-service"\n'
        'version = "0.2.0"\n'
        'dependencies = ["fastapi>=0.115.0", "uvicorn>=0.30.0", "pydantic>=2.0.0"]\n\n'
        "[project.scripts]\n"
        'start = "app.main:run"\n'
    )
    (tmp_path / "pyproject.toml").write_text(pyproject_data, encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest>=8.0.0\n# comment\nruff\n", encoding="utf-8")

    tool = ProjectInspectTool(allowed_root=tmp_path)
    res = await tool.execute({"path": str(tmp_path)})

    assert "Python" in res["technologies"]
    assert "FastAPI" in res["technologies"]
    assert "Uvicorn" in res["technologies"]
    assert "pyproject.toml" in res["manifests_detected"]
    assert "requirements.txt" in res["manifests_detected"]
    assert "start" in res["scripts"]
    assert any("fastapi" in d for d in res["dependencies"]["python"])
    assert any("pytest" in d for d in res["dependencies"]["python"])


@pytest.mark.asyncio
async def test_inspect_rust_cargo_project(tmp_path: Path):
    cargo_data = (
        "[package]\n"
        'name = "yana-core"\n'
        'version = "0.1.0"\n\n'
        "[dependencies]\n"
        'serde = "1.0"\n'
        'tokio = { version = "1.0", features = ["full"] }\n'
    )
    (tmp_path / "Cargo.toml").write_text(cargo_data, encoding="utf-8")

    tool = ProjectInspectTool(allowed_root=tmp_path)
    res = await tool.execute({"path": str(tmp_path)})

    assert "Rust" in res["technologies"]
    assert "Cargo.toml" in res["manifests_detected"]
    assert "serde" in res["dependencies"]["cargo"]
    assert "tokio" in res["dependencies"]["cargo"]


@pytest.mark.asyncio
async def test_inspect_git_detection(tmp_path: Path):
    # Simulate git repo layout
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/feature/dev-assistant\n", encoding="utf-8")

    tool = ProjectInspectTool(allowed_root=tmp_path)
    res = await tool.execute({"path": str(tmp_path)})

    assert res["git"]["is_repo"] is True
    assert res["git"]["branch"] in ("feature/dev-assistant", None)
