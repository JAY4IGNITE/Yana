import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Strongly typed application configuration with environment separation."""

    model_config = SettingsConfigDict(
        env_prefix="YANA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Environment: development, testing, or production
    env: Literal["development", "testing", "production"] = "development"
    debug: bool = True

    # Network / Server
    agent_host: str = "127.0.0.1"
    agent_port: int = 8765
    agent_log_level: str = "INFO"

    # Storage
    storage_path: Path = Path("./data/yana.db")

    # AI Configuration (Secrets stored as SecretStr)
    ai_provider: str = "mock"
    ai_api_key: SecretStr = Field(default=SecretStr(""))
    ai_base_url: str | None = None
    ai_model: str = "gpt-4o-mini"
    ai_max_tokens: int = 2048
    ai_temperature: float = 0.7
    ai_system_prompt: str = (
        "You are YANA, a personal, native Windows AI desktop companion. "
        "Keep your responses concise, helpful, and natural."
    )

    # Security & Policy
    permission_mode: Literal["strict", "permissive"] = "strict"
    max_execution_loops: int = 10
    tool_timeout_seconds: int = 30

    def model_post_init(self, __context: Any) -> None:
        """Enforce production security invariants upon settings initialization."""
        super().model_post_init(__context)
        if self.env == "production":
            # In production, debug mode must ALWAYS be disabled
            self.debug = False
            # Host must strictly bind to localhost for IPC security
            self.agent_host = "127.0.0.1"
            # Route persistent storage to user LocalAppData if default relative path
            if self.storage_path == Path("./data/yana.db"):
                local_app_data = os.environ.get("LOCALAPPDATA")
                if local_app_data:
                    self.storage_path = Path(local_app_data) / "YANA" / "data" / "yana.db"
                else:
                    self.storage_path = Path.home() / ".yana" / "data" / "yana.db"

    def safe_dict(self) -> dict[str, object]:
        """Export settings with sensitive credentials redacted."""
        data = self.model_dump()
        # Explicitly mask secrets
        if self.ai_api_key.get_secret_value():
            data["ai_api_key"] = "********"
        else:
            data["ai_api_key"] = ""
        # Convert Path to str
        data["storage_path"] = str(self.storage_path)
        return data


# Singleton settings instance
settings = AgentSettings()
