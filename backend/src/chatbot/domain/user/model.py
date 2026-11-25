from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import StringConstraints

from chatbot.domain.errors import Conflict, NotFound, Unauthorized
from chatbot.domain.validated import Validated


class UsernameTaken(Conflict):
    code = "username_taken"


class InvalidCredentials(Unauthorized):
    """Unknown username or wrong password (deliberately not told apart)."""

    code = "invalid_credentials"


class InvalidToken(Unauthorized):
    """The bearer token is malformed, badly signed or has no subject."""

    code = "invalid_token"


class TokenExpired(InvalidToken):
    code = "token_expired"


class UserNotFound(NotFound):
    code = "user_not_found"


Language = Literal["en", "it", "de"]
"""UI + assistant reply language."""


Username = Annotated[str, StringConstraints(pattern=r"\S")]
"""Must contain a non-space character; kept as typed (not stripped)."""


@dataclass
class User(Validated):
    """An account that owns conversations. Auth is JWT bearer + bcrypt; the
    ``hashed_password`` is the bcrypt digest (never the plaintext)."""

    id: UUID
    username: Username
    hashed_password: str
    created_at: datetime
    # UI + assistant reply language: one of 'en' | 'it' | 'de'. 'en' is the
    # default and fallback.
    language: Language = "en"
