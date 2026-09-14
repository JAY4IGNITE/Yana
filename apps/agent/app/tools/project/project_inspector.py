"""Project Inspection Tool for YANA Developer Assistant.

Inspects software repositories, identifying project structure, technology stacks,
configuration manifests (package.json, pyproject.toml, requirements.txt, Cargo.toml),
scripts, dependencies, README summaries, and Git version-control state.
"""

import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from app.errors import ToolError, ValidationError
from app.logger import logger
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool
from app.tools.security_policy import validate_safe_path

# Common ignored directories during project structure analysis
IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    "dist",
    "build",
    ".next",
    ".turbo",
}


class ProjectInspectTool(BaseTool):
    """Safely inspects a software project directory to extract architecture and metadata."""

    name = "project.inspect"
    category = "project"
    description = (
        "Inspects a project repository, detecting technology stack, package manifests "
        "(package.json, pyproject.toml, Cargo.toml, requirements.txt), scripts, dependencies, "
        "directory layout, and Git version control status."
    )
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the project directory to inspect (defaults to '.')",
                "default": ".",
            },
        },
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        path_str = arguments.get("path", ".")
        if not isinstance(path_str, str):
            raise ValidationError("Argument 'path' must be a string if provided.")

        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)
        if not resolved.is_dir():
            raise ValidationError(f"Path '{path_str}' is not a directory.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path_str = arguments.get("path", ".")
        target_dir = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)

        try:
            structure = self._inspect_structure(target_dir)
            manifests_info: dict[str, Any] = {}
            technologies: set[str] = set()
            all_scripts: dict[str, str] = {}
            all_dependencies: dict[str, list[str]] = {}

            # 1. Inspect package.json
            pkg_json = target_dir / "package.json"
            if pkg_json.is_file():
                pkg_data = self._parse_package_json(pkg_json)
                manifests_info["package.json"] = pkg_data
                technologies.add("Node.js / JavaScript")
                if (target_dir / "tsconfig.json").is_file():
                    technologies.add("TypeScript")
                all_scripts.update(pkg_data.get("scripts", {}))
                deps = list(pkg_data.get("dependencies", {}).keys())
                dev_deps = list(pkg_data.get("devDependencies", {}).keys())
                all_dependencies["npm"] = deps + dev_deps

                # Detect frameworks from dependencies
                combined_deps = set(deps + dev_deps)
                if "@tauri-apps/api" in combined_deps or (target_dir / "src-tauri").is_dir():
                    technologies.add("Tauri")
                if "react" in combined_deps:
                    technologies.add("React")
                if "vue" in combined_deps:
                    technologies.add("Vue")
                if "vite" in combined_deps:
                    technologies.add("Vite")
                if "next" in combined_deps:
                    technologies.add("Next.js")

            # 2. Inspect pyproject.toml
            pyproject = target_dir / "pyproject.toml"
            if pyproject.is_file():
                py_data = self._parse_pyproject_toml(pyproject)
                manifests_info["pyproject.toml"] = py_data
                technologies.add("Python")
                py_deps = py_data.get("dependencies", [])
                all_dependencies["python"] = py_deps
                all_scripts.update(py_data.get("scripts", {}))

                if any("fastapi" in d.lower() for d in py_deps):
                    technologies.add("FastAPI")
                if any("uvicorn" in d.lower() for d in py_deps):
                    technologies.add("Uvicorn")

            # 3. Inspect requirements.txt
            req_txt = target_dir / "requirements.txt"
            if req_txt.is_file():
                req_deps = self._parse_requirements_txt(req_txt)
                manifests_info["requirements.txt"] = {"dependencies": req_deps}
                technologies.add("Python")
                existing = all_dependencies.get("python", [])
                all_dependencies["python"] = list(set(existing + req_deps))

            # 4. Inspect Cargo.toml
            cargo_toml = target_dir / "Cargo.toml"
            if cargo_toml.is_file():
                cargo_data = self._parse_cargo_toml(cargo_toml)
                manifests_info["Cargo.toml"] = cargo_data
                technologies.add("Rust")
                cargo_deps = cargo_data.get("dependencies", [])
                all_dependencies["cargo"] = cargo_deps

            # 5. Inspect README
            readme_summary = self._read_readme_summary(target_dir)

            # 6. Inspect Git State
            git_state = self._inspect_git_state(target_dir)

            if not technologies:
                technologies.add("Generic / Unknown")

            return {
                "path": str(target_dir),
                "technologies": sorted(technologies),
                "manifests_detected": sorted(manifests_info.keys()),
                "manifests": manifests_info,
                "scripts": all_scripts,
                "dependencies": all_dependencies,
                "git": git_state,
                "readme_summary": readme_summary,
                "structure": structure,
            }
        except Exception as e:
            logger.error("Project inspection failed for %s: %s", target_dir, e)
            raise ToolError(f"Failed to inspect project at '{target_dir}': {e}") from e

    def _inspect_structure(self, target_dir: Path) -> dict[str, Any]:
        """List top-level directories and files, filtering out noisy folders."""
        dirs: list[str] = []
        files: list[str] = []

        try:
            for item in target_dir.iterdir():
                if item.name.startswith(".") and item.name != ".git":
                    continue
                if item.is_dir():
                    if item.name not in IGNORED_DIRS:
                        dirs.append(item.name)
                elif item.is_file():
                    files.append(item.name)
        except OSError as e:
            logger.warning("Could not read directory structure of %s: %s", target_dir, e)

        return {
            "top_level_directories": sorted(dirs),
            "top_level_files": sorted(files),
        }

    def _parse_package_json(self, path: Path) -> dict[str, Any]:
        """Parse package.json with error tolerance."""
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            return {
                "name": data.get("name"),
                "version": data.get("version"),
                "scripts": data.get("scripts", {}),
                "dependencies": data.get("dependencies", {}),
                "devDependencies": data.get("devDependencies", {}),
            }
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
            return {"error": f"Failed to parse package.json: {e}"}

    def _parse_pyproject_toml(self, path: Path) -> dict[str, Any]:
        """Parse pyproject.toml extracting dependencies and scripts."""
        try:
            content = path.read_text(encoding="utf-8")
            data = tomllib.loads(content)

            proj = data.get("project", {})
            name = proj.get("name")
            version = proj.get("version")
            deps = proj.get("dependencies", [])
            scripts = proj.get("scripts", {})

            # Also check poetry if present
            tool_poetry = data.get("tool", {}).get("poetry", {})
            if tool_poetry:
                name = name or tool_poetry.get("name")
                version = version or tool_poetry.get("version")
                poetry_deps = list(tool_poetry.get("dependencies", {}).keys())
                deps = list(set(deps + poetry_deps))
                scripts.update(tool_poetry.get("scripts", {}))

            return {
                "name": name,
                "version": version,
                "dependencies": deps,
                "scripts": scripts,
            }
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
            return {"error": f"Failed to parse pyproject.toml: {e}"}

    def _parse_requirements_txt(self, path: Path) -> list[str]:
        """Parse requirements.txt into clean dependency specs."""
        deps: list[str] = []
        try:
            content = path.read_text(encoding="utf-8")
            for line in content.splitlines():
                clean = line.strip()
                if clean and not clean.startswith("#") and not clean.startswith("-"):
                    deps.append(clean)
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
        return deps

    def _parse_cargo_toml(self, path: Path) -> dict[str, Any]:
        """Parse Cargo.toml extracting package details and dependencies."""
        try:
            content = path.read_text(encoding="utf-8")
            data = tomllib.loads(content)
            pkg = data.get("package", {})
            deps = list(data.get("dependencies", {}).keys())
            dev_deps = list(data.get("dev-dependencies", {}).keys())
            return {
                "name": pkg.get("name"),
                "version": pkg.get("version"),
                "dependencies": deps + dev_deps,
            }
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
            return {"error": f"Failed to parse Cargo.toml: {e}"}

    def _read_readme_summary(self, target_dir: Path) -> str | None:
        """Find and read an initial summary snippet from a README file."""
        candidates = ["README.md", "README.txt", "README.rst", "README"]
        for candidate in candidates:
            p = target_dir / candidate
            if p.is_file():
                try:
                    text = p.read_text(encoding="utf-8", errors="replace").strip()
                    # Return first 500 characters
                    if len(text) > 500:
                        return text[:500] + "..."
                    return text
                except OSError:
                    pass
        return None

    def _inspect_git_state(self, target_dir: Path) -> dict[str, Any]:
        """Determine Git repository state including branch, cleanliness, and recent commits."""
        git_dir = target_dir / ".git"
        if not git_dir.exists():
            return {
                "is_repo": False,
                "branch": None,
                "clean": True,
                "uncommitted_files": [],
                "recent_commits": [],
            }

        branch: str | None = None
        uncommitted: list[str] = []
        clean = True
        recent_commits: list[str] = []

        # Try using git CLI first
        try:
            # Current branch
            res_branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res_branch.returncode == 0 and res_branch.stdout.strip():
                branch = res_branch.stdout.strip()

            # Status
            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res_status.returncode == 0:
                lines = [line.strip() for line in res_status.stdout.splitlines() if line.strip()]
                uncommitted = lines
                clean = len(lines) == 0

            # Recent commits
            res_log = subprocess.run(
                ["git", "log", "-n", "3", "--oneline"],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res_log.returncode == 0:
                recent_commits = [
                    line.strip() for line in res_log.stdout.splitlines() if line.strip()
                ]
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            # Fallback: direct read of .git/HEAD
            try:
                head_file = git_dir / "HEAD"
                if head_file.is_file():
                    head_content = head_file.read_text(encoding="utf-8").strip()
                    if head_content.startswith("ref: refs/heads/"):
                        branch = head_content.replace("ref: refs/heads/", "").strip()
            except OSError:
                pass

        return {
            "is_repo": True,
            "branch": branch,
            "clean": clean,
            "uncommitted_files": uncommitted[:20],
            "uncommitted_count": len(uncommitted),
            "recent_commits": recent_commits,
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and "technologies" in output
        if verified:
            tech_str = ", ".join(output["technologies"])
            manifests = ", ".join(output.get("manifests_detected", [])) or "None"
            notes = f"Project inspected: {tech_str}. Manifests: {manifests}."
        else:
            notes = "Inspection did not return structured project data."

        return VerificationResult(
            task_id="project",
            tool_call_id="project.inspect",
            verified=verified,
            notes=notes,
        )
