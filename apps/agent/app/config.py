"""Application Configuration for YANA Agent."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Strongly typed application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="YANA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Environment
    env: Literal["development", "staging", "production"] = "development"
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
