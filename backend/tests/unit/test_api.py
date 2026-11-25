"""HTTP-level tests: the real FastAPI app over in-memory fakes (no DB, no network).

`api` builds a fresh app per test and points every adapter dependency at the
fakes in `fakes.py`. Logging goes to stdout (canonical setup), read with `capsys`.
"""

from datetime import UTC, datetime, timedelta
from functools import cached_property
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chatbot.adapters.security.bcrypt.bcrypt_password_hasher import BcryptPasswordHasher
from chatbot.adapters.security.fake.fake_password_hasher import FakePasswordHasher
from chatbot.domain.conversation.model import Attachment, Conversation
from chatbot.domain.user.model import User
from chatbot.entrypoints import dependencies
from chatbot.entrypoints.logging_setup import configure_logging
from chatbot.entrypoints.main import create_app
from chatbot.entrypoints.routers.limiter import limiter
from chatbot.entrypoints.settings import get_settings
from tests.unit.fakes import FakeAttachmentStorage, FakeLLM, make_uow_factory


class Api:
    """The app is built on first use, inside the test body: pytest's `capsys`
    only captures there. The client isn't entered as a context manager, so
    `lifespan` doesn't run; `app` sets up the stdout logging itself."""

    def __init__(self) -> None:
        self.conversations: dict[UUID, Conversation] = {}
        self.attachments: dict[UUID, Attachment] = {}
        self.users: dict[UUID, User] = {}
        self.storage = FakeAttachmentStorage()

    @cached_property
    def app(self) -> FastAPI:
        configure_logging()
        app = create_app()
        uow_factory = make_uow_factory(self.conversations, self.attachments, self.users)
        app.dependency_overrides[dependencies.get_uow_factory] = lambda: uow_factory
        app.dependency_overrides[dependencies.get_user_uow_factory] = lambda: uow_factory
        app.dependency_overrides[dependencies.get_llm] = lambda: FakeLLM(["Hi", "!"])
        app.dependency_overrides[dependencies.get_attachment_storage] = lambda: self.storage
        app.dependency_overrides[dependencies.get_password_hasher] = FakePasswordHasher
        return app

    @cached_property
    def client(self) -> TestClient:
        return TestClient(self.app, raise_server_exceptions=False)

    def login(self, username: str = "alice", password: str = "secret-pw") -> dict[str, str]:
        """Register (if needed) and log in; returns the bearer header."""
        self.client.post("/auth/register", json={"username": username, "password": password})
        response = self.client.post(
            "/auth/login", json={"username": username, "password": password}
        )
        return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "1000/minute")
    monkeypatch.setenv("ATTACHMENT_MAX_BYTES", "16")
    get_settings.cache_clear()
    limiter.reset()
    yield Api()
    get_settings.cache_clear()
    limiter.reset()


def _access_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if " app.access " in line]


def test_responses_carry_a_request_id_header(api):
    response = api.client.get("/health")

    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 12


def test_access_line_names_the_request_id(api, capsys):
    headers = api.login()
    capsys.readouterr()

    response = api.client.get("/conversations/", headers=headers)

    request_id = response.headers["X-Request-ID"]
    lines = _access_lines(capsys.readouterr().out)
    assert len(lines) == 1
    assert f"req={request_id}" in lines[0]
    assert "GET /conversations/ -> 200" in lines[0]


def test_health_writes_no_access_line(api, capsys):
    capsys.readouterr()

    api.client.get("/health")

    assert _access_lines(capsys.readouterr().out) == []


def test_unexpected_error_is_logged_with_traceback_and_hidden(api, capsys):
    def boom() -> None:
        raise ZeroDivisionError("secret internals")

    api.app.add_api_route("/boom", boom, methods=["GET"])
    capsys.readouterr()

    response = api.client.get("/boom")

    output = capsys.readouterr().out
    assert response.status_code == 500
    assert "secret internals" not in response.text
    assert "Traceback" in output
    assert "ZeroDivisionError: secret internals" in output


# ── D2: conversation errors ──────────────────────────────────────────────────

_MISSING = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "code"),
    [
        ("get", f"/conversations/{_MISSING}", {}, "conversation_not_found"),
        ("patch", f"/conversations/{_MISSING}", {"json": {"title": "x"}}, "conversation_not_found"),
        (
            "post",
            f"/conversations/{_MISSING}/attachments",
            {"files": {"file": ("a.txt", b"hi", "text/plain")}},
            "conversation_not_found",
        ),
        (
            "get",
            f"/conversations/{_MISSING}/attachments/{_MISSING}",
            {},
            "conversation_not_found",
        ),
    ],
)
def test_unknown_conversation_is_404(api, method, path, kwargs, code):
    headers = api.login()

    response = getattr(api.client, method)(path, headers=headers, **kwargs)

    assert response.status_code == 404
    assert response.json() == {"code": code, "message": response.json()["message"], "field": None}


def test_another_users_conversation_is_404(api):
    owner = api.login("alice")
    conversation_id = api.client.post("/conversations/", headers=owner).json()["id"]
    intruder = api.login("bob")

    response = api.client.get(f"/conversations/{conversation_id}", headers=intruder)

    assert response.status_code == 404
    assert response.json()["code"] == "conversation_not_found"


def test_unknown_attachment_is_404(api):
    headers = api.login()
    conversation_id = api.client.post("/conversations/", headers=headers).json()["id"]

    response = api.client.get(
        f"/conversations/{conversation_id}/attachments/{_MISSING}", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["code"] == "attachment_not_found"


def test_oversized_upload_is_413(api):
    headers = api.login()
    conversation_id = api.client.post("/conversations/", headers=headers).json()["id"]

    response = api.client.post(
        f"/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("big.txt", b"x" * 17, "text/plain")},  # limit is 16 bytes here
    )

    assert response.status_code == 413
    assert response.json() == {
        "code": "attachment_too_large",
        "message": "attachment exceeds 16 bytes",
        "field": "file",
    }


# ── D2: auth errors ──────────────────────────────────────────────────────────


def _token(sub: str, minutes: int) -> str:
    settings = get_settings()
    expires = datetime.now(tz=UTC) + timedelta(minutes=minutes)
    return jwt.encode(
        {"sub": sub, "exp": expires}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def test_duplicate_username_is_409(api):
    api.login("alice")

    response = api.client.post("/auth/register", json={"username": "alice", "password": "pw-2"})

    assert response.status_code == 409
    assert response.json()["code"] == "username_taken"


@pytest.mark.parametrize(("username", "password"), [("alice", "wrong-pw"), ("nobody", "x")])
def test_bad_login_is_401(api, username, password):
    api.login("alice")

    response = api.client.post("/auth/login", json={"username": username, "password": password})

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_credentials",
        "message": "Invalid username or password",
        "field": None,
    }


def test_password_over_72_bytes_registers_and_logs_in(api):
    api.app.dependency_overrides[dependencies.get_password_hasher] = lambda: BcryptPasswordHasher(
        rounds=4
    )
    body = {"username": "alice", "password": "a long passphrase " * 5}  # 90 bytes

    registered = api.client.post("/auth/register", json=body)
    logged_in = api.client.post("/auth/login", json=body)

    assert registered.status_code == 201
    assert logged_in.status_code == 200
    assert logged_in.json()["access_token"]


def _tampered(token: str) -> str:
    header, payload, signature = token.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    return f"{header}.{payload}.{flipped}"


def test_token_issued_by_the_old_code_is_accepted(api):
    settings = get_settings()
    expires = datetime.now(tz=UTC) + timedelta(minutes=5)
    old_style = jwt.encode(  # exactly what the removed _auth.create_access_token wrote
        {"sub": str(uuid4()), "username": "alice", "exp": expires},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = api.client.get("/conversations/", headers={"Authorization": f"Bearer {old_style}"})

    assert response.status_code == 200


def test_valid_token_is_accepted(api):
    token = _token(str(uuid4()), minutes=5)

    response = api.client.get("/conversations/", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("make_token", "code"),
    [
        (lambda: _token(str(uuid4()), minutes=-5), "token_expired"),
        (lambda: "not-a-jwt", "invalid_token"),
        (lambda: _token("not-a-uuid", minutes=5), "invalid_token"),
        (lambda: _tampered(_token(str(uuid4()), minutes=5)), "invalid_token"),
    ],
)
def test_bad_token_is_401(api, make_token, code):
    headers = {"Authorization": f"Bearer {make_token()}"}

    response = api.client.get("/conversations/", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == code


def test_unknown_user_profile_is_404(api):
    token = _token(str(uuid4()), minutes=5)

    response = api.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404
    assert response.json()["code"] == "user_not_found"


def test_login_over_the_rate_limit_is_429(api, monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()
    body = {"username": "alice", "password": "wrong-pw"}
    for _ in range(2):
        api.client.post("/auth/login", json=body)

    response = api.client.post("/auth/login", json=body)

    assert response.status_code == 429
    assert response.json()["code"] == "http_429"
    assert set(response.json()) == {"code", "message", "field"}
