"""Chatbot's settings (Blueprint v2, D4). Built once, validated at startup.

The API (`dependencies.py`) and the CLI (`cli/dependencies.py`) both read them.
`DATABASE_URL` (or the `DB_*` parts) and `LOG_LEVEL` come from `AppSettings`.
"""

from functools import lru_cache

from pydantic import ValidationError, field_validator

from chatbot.domain.user.model import Language
from chatbot.entrypoints.settings_base import AppSettings


class Settings(AppSettings):
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_chat_enable_thinking: bool = False
    system_prompt: str = "You are a helpful assistant."
    # Auth (Phase 7): JWT bearer + bcrypt. `jwt_secret_key` is required (no
    # default; `make env` generates it). Token lifetime defaults to 30 days
    # (LAN app). `login_rate_limit` is a slowapi string; e2e overrides it.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 43200
    login_rate_limit: str = "5/minute"
    # Attachment storage (Garage / S3). Leave GARAGE_ENDPOINT empty to fall back
    # to in-memory NullAttachmentStorage (mirrors the LLM mock fallback).
    garage_endpoint: str = ""
    garage_access_key_id: str = ""
    garage_secret_access_key: str = ""
    garage_bucket: str = "chatbot"
    garage_region: str = "garage"
    # Upload caps. Reject blobs over this size; truncate extracted text to bound
    # the LLM context budget.
    attachment_max_bytes: int = 10 * 1024 * 1024
    attachment_max_extracted_chars: int = 40_000
    # Web access (Phase 6). `web_tools_enabled` off ⇒ mock search/fetch adapters
    # (offline dev/tests). Caps bound the tool loop and each page fetch.
    web_tools_enabled: bool = True
    web_tool_max_iterations: int = 4
    web_search_max_results: int = 5
    web_fetch_max_chars: int = 20_000
    # CLI only. CHATBOT_CLI_USER names the acting user (empty = the sole user);
    # CHATBOT_LANGUAGE is the CLI's reply language.
    chatbot_cli_user: str = ""
    chatbot_language: Language = "en"

    @field_validator("chatbot_cli_user", mode="before")
    @classmethod
    def _strip_cli_user(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("chatbot_language", mode="before")
    @classmethod
    def _normalise_language(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() or "en"
        return value

    def async_database_url(self) -> str:
        return self.sqlalchemy_url("postgresql+asyncpg")


@lru_cache
def get_settings() -> Settings:
    # Required fields come from the environment, which pyright cannot see.
    return Settings()  # pyright: ignore[reportCallIssue]


def describe_settings_error(exc: ValidationError) -> str:
    """One line per problem, naming the environment variable at fault."""
    lines = []
    for error in exc.errors():
        names = [str(part).upper() for part in error.get("loc", ())]
        prefix = f"{'.'.join(names)}: " if names else ""
        lines.append(f"{prefix}{error.get('msg', 'invalid')}")
    return "Invalid settings — " + "; ".join(lines)
