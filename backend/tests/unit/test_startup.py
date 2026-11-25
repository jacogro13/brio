import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect as sa_inspect

from chatbot.adapters.persistence.postgres import orm
from chatbot.domain.conversation.model import Attachment, Conversation, Message
from chatbot.domain.user.model import User
from chatbot.entrypoints.main import create_app
from chatbot.entrypoints.settings import get_settings


@pytest.fixture
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_app_startup_maps_domain_entities():
    orm.mapper_registry.dispose()  # other tests may have mapped them already

    with TestClient(create_app()):
        # sa_inspect raises NoInspectionAvailable for a class that isn't mapped.
        mappers = [sa_inspect(cls) for cls in (User, Conversation, Message, Attachment)]

    assert all(mapper is not None for mapper in mappers)


def test_importing_the_app_needs_no_env_vars():
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/")}

    result = subprocess.run(
        [sys.executable, "-c", "import chatbot.entrypoints.main"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("missing", ["JWT_SECRET_KEY", "DATABASE_URL"])
def test_startup_without_a_required_setting_fails(monkeypatch, fresh_settings, missing):
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError), TestClient(create_app()):
        pass


def test_health_is_not_in_the_schema_but_still_answers():
    app = create_app()

    response = TestClient(app).get("/health")

    assert response.json() == {"status": "ok"}
    assert "/health" not in app.openapi()["paths"]
