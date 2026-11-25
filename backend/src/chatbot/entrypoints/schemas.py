from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from chatbot.domain.conversation.model import MaxTokens, Role, Temperature
from chatbot.domain.user.model import Language

# Supported UI + assistant languages; keep in sync with
# services/conversation/language.py::SUPPORTED_LANGUAGES.


class AttachmentResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size: int
    # True when the model can read the file's text; False for images / anything
    # unextractable (stored, but not sent to the LLM). Drives the UI badge.
    has_text: bool
    created_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    role: Role
    content: str
    thinking: str | None = None
    created_at: datetime
    attachments: list[AttachmentResponse] = []
    # Web-access tool activity (Phase 6) — per-call records; null when none ran.
    tool_events: list[dict] | None = None


class ConversationSummaryResponse(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime


class ConversationResponse(BaseModel):
    id: UUID
    title: str | None
    messages: list[MessageResponse]
    created_at: datetime
    # Per-conversation LLM overrides — null means "use the server default".
    temperature: Temperature | None = None
    max_tokens: MaxTokens | None = None
    system_prompt_override: str | None = None


class SendMessageRequest(BaseModel):
    content: str
    # Ids of previously-uploaded, still-pending attachments to link to this turn.
    attachment_ids: list[UUID] = []
    # Web access (Phase 6) — per-message toggle; runs the prompted-JSON tool loop
    # (search + page fetch) with thinking forced off for this turn.
    web_access: bool = False
    # Thinking — per-message toggle (like web access). null → server default.
    # Ignored when web_access is on (the tool loop forces thinking off).
    enable_thinking: bool | None = None


class UpdateConversationRequest(BaseModel):
    """Partial update. Every field is optional; only fields actually present in
    the request body are applied (``model_dump(exclude_unset=True)``), so an
    explicit ``null`` resets a setting while an omitted field is left untouched."""

    title: str | None = None
    temperature: Temperature | None = None
    max_tokens: MaxTokens | None = None
    system_prompt_override: str | None = None


class RegenerateRequest(BaseModel):
    # Thinking — per-message toggle carried on the turn. null → server default.
    enable_thinking: bool | None = None


class EditMessageRequest(BaseModel):
    content: str
    # Thinking — per-message toggle carried on the turn. null → server default.
    enable_thinking: bool | None = None


# --- Auth (Phase 7) ---


class RegisterRequest(BaseModel):
    username: str
    password: str
    # Browser-detected language the frontend sends at sign-up; defaults to 'en'.
    language: Language = "en"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str


class ProfileResponse(BaseModel):
    """The acting user's profile — source of truth the frontend fetches on load
    to seed the language switcher."""

    username: str
    language: Language


class UpdateLanguageRequest(BaseModel):
    language: Language


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
