import pytest
from pydantic import ValidationError

from chatbot.entrypoints.cli import dependencies as cli_dependencies
from chatbot.entrypoints.cli.main import main as cli_main
from chatbot.entrypoints.settings import Settings, get_settings

_ENV_NAMES = (
    "DATABASE_URL",
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "JWT_SECRET_KEY",
    "CHATBOT_LANGUAGE",
    "CHATBOT_CLI_USER",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_missing_jwt_secret_is_an_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/chatbot")

    with pytest.raises(ValidationError) as excinfo:
        get_settings()

    assert "jwt_secret_key" in str(excinfo.value)


def test_missing_database_settings_is_an_error(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")

    with pytest.raises(ValidationError) as excinfo:
        get_settings()

    assert "DATABASE_URL" in str(excinfo.value)


@pytest.mark.parametrize(
    ("env", "expected_url"),
    [
        (
            {"DATABASE_URL": "postgresql+asyncpg://u:p@db:5432/chatbot"},
            "postgresql+asyncpg://u:p@db:5432/chatbot",
        ),
        (
            {"DB_USER": "chatbot_app", "DB_PASSWORD": "p@ss", "DB_NAME": "chatbot"},
            "postgresql+asyncpg://chatbot_app:p%40ss@localhost:5432/chatbot",
        ),
    ],
)
def test_database_url_or_db_parts_are_accepted(monkeypatch, env, expected_url):
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    settings = get_settings()

    assert settings.async_database_url() == expected_url


@pytest.mark.parametrize(("raw", "expected"), [("IT", "it"), ("  de ", "de"), ("", "en")])
def test_cli_language_is_normalised(monkeypatch, raw, expected):
    monkeypatch.setenv("CHATBOT_LANGUAGE", raw)

    settings = Settings(database_url="postgresql://x", jwt_secret_key="secret")

    assert settings.chatbot_language == expected


def test_unknown_cli_language_is_an_error(monkeypatch):
    monkeypatch.setenv("CHATBOT_LANGUAGE", "fr")

    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://x", jwt_secret_key="secret")


def test_cli_reports_missing_setting_by_name(monkeypatch, capsys):
    monkeypatch.setattr(cli_dependencies, "_find_dotenv", lambda: None)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/chatbot")

    with pytest.raises(SystemExit) as excinfo:
        cli_main()

    assert excinfo.value.code == 1
    assert "JWT_SECRET_KEY" in capsys.readouterr().out
