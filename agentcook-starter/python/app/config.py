"""Configuration — every knob comes from environment variables or `.env`."""

from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=("settings_",))

    # --- LLM ---------------------------------------------------------------
    # Mock mode is ON by default: clone, `make dev`, chat — no API key needed.
    # The mock model speaks the same API as the real one, so the ReAct loop,
    # the tools and the UI all run for real; only the "thinking" is scripted.
    mock_mode: bool = True
    anthropic_api_key: str = ""
    # Point at any Anthropic-compatible endpoint (a proxy, or a provider that
    # speaks the Anthropic Messages API). Empty = the official API.
    anthropic_base_url: str = ""
    # Empty = the newest Sonnet model your key can use (looked up via the Models API).
    # Set it to pin a specific model id.
    model_name: str = ""
    max_tokens: int = 2048

    # --- Agent loop --------------------------------------------------------
    max_reasoning_rounds: int = 8  # LLM calls per user message, at most
    max_context_messages: int = 20  # history kept per session (see context.py)
    tool_timeout_seconds: float = 15.0
    max_tool_result_chars: int = 3000  # longer results are truncated before the LLM sees them
    max_sessions: int = 1000  # in-memory sessions kept; least recently used are dropped

    # --- Go-live (chapter 25) ----------------------------------------------
    enable_input_guard: bool = True  # block obvious prompt-injection attempts
    allowed_users: str = ""  # comma-separated beta allowlist; empty = everyone
    cors_origins: str = "*"
    log_level: str = "INFO"

    # --- Tool credentials (chapter 24) -------------------------------------
    qweather_api_key: str = ""
    qweather_api_host: str = ""  # your project's API Host from the QWeather console
    scraper_api_key: str = ""
    sales_db_path: str = "data/sales.db"

    @property
    def allowed_user_set(self) -> set[str]:
        return {u.strip() for u in self.allowed_users.split(",") if u.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
