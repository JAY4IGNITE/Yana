import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Strongly typed application configuration with environment separation."""

    model_config = SettingsConfigDict(
        env_prefix="YANA_",
        env_file=(".env", "../../.env", "../.env"),
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

    # Storage & Memory Engine
    storage_path: Path = Path("./data/yana.db")
    memory_backend: Literal["sqlite", "postgres"] = "sqlite"
    postgres_dsn: SecretStr = Field(
        default=SecretStr("postgresql://postgres:postgres@localhost:5432/yana")
    )

    # AI Configuration & Tiered Routing
    ai_provider: str = "nvidia"  # Default active or primary
    ai_api_key: SecretStr = Field(default=SecretStr(""))
    ai_base_url: str | None = None
    ai_model: str = "meta/llama-3.2-11b-vision-instruct"
    ai_max_tokens: int = 2048
    ai_temperature: float = 0.7
    ai_system_prompt: str = (
        "You are YANA, an intelligent, helpful, and native Windows AI desktop companion. "
        "Directly answer questions, solve problems, and help the user. "
        "Be direct, accurate, and concise. Do not repeat introductions or re-introduce "
        "yourself unless explicitly asked."
    )

    # 🧠 Local Tier (Ollama)
    ai_local_provider: str = "ollama"
    ai_local_base_url: str = "http://localhost:11434/v1"
    ai_local_model: str = "llama3.2"

    # 🚀 Heavy Reasoning & Multimodal Tier (NVIDIA NIM)
    ai_heavy_provider: str = "nvidia"
    ai_heavy_base_url: str = "https://integrate.api.nvidia.com/v1"
    ai_heavy_model: str = "meta/llama-3.2-11b-vision-instruct"
    ai_heavy_api_key: SecretStr = Field(default=SecretStr(""))

    # ☁️ Fallback Cloud Tier
    ai_fallback_provider: str = "openai"
    ai_fallback_base_url: str | None = None
    ai_fallback_model: str = "gpt-4o-mini"
    ai_fallback_api_key: SecretStr = Field(default=SecretStr(""))

    # Routing strategy: 'auto' (smart routing), 'local' (force local), 'heavy' (force NIM)
    ai_routing_mode: Literal["auto", "local", "heavy", "fallback"] = "auto"

    # 🎤 Voice & Audio Subsystem
    stt_provider: str = "nvidia_parakeet"
    stt_model: str = "nvidia/parakeet-ctc-1.1b-asr"
    tts_provider: str = "edge_tts"
    tts_voice: str = "en-US-AriaNeural"

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
