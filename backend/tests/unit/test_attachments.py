from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from chatbot.domain.conversation.model import (
    Attachment,
    AttachmentTooLarge,
    Conversation,
    ConversationNotFound,
    Message,
)
from chatbot.domain.conversation.ports.text_extractor import AbstractTextExtractor
from chatbot.services.conversation._streaming import build_history, render_user_content
from chatbot.services.conversation.delete_conversation import DeleteConversationUseCase
from chatbot.services.conversation.send_message import SendMessageUseCase
from chatbot.services.conversation.upload_attachment import UploadAttachmentUseCase
from tests.unit.fakes import USER_ID, FakeAttachmentStorage, FakeLLM, make_uow_factory

SYSTEM_PROMPT = "You are a helpful assistant."


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _conv() -> Conversation:
    return Conversation(id=uuid4(), title=None, messages=[], created_at=_now())


def _attachment(conversation_id: UUID, text: str | None) -> Attachment:
    aid = uuid4()
    return Attachment(
        id=aid,
        conversation_id=conversation_id,
        message_id=None,
        filename="notes.md",
        content_type="text/markdown",
        size=10,
        s3_key=f"conversations/{conversation_id}/{aid}/notes.md",
        extracted_text=text,
        created_at=_now(),
    )


async def _collect(agen) -> list[dict]:
    return [event async for event in agen]


class _Extractor(AbstractTextExtractor):
    def __init__(self, text: str | None) -> None:
        self._text = text

    async def extract(self, filename: str, content_type: str, data: bytes) -> str | None:
        return self._text


# ── pure helpers ──────────────────────────────────────────────────────────────


def test_render_user_content_inlines_extracted_text():
    a = _attachment(uuid4(), "file body")
    out = render_user_content("look at this", [a])
    assert "look at this" in out
    assert "[Attached file: notes.md]" in out
    assert "file body" in out


def test_render_user_content_notes_unextractable():
    a = _attachment(uuid4(), None)
    out = render_user_content("pic", [a])
    assert "not visible to the model" in out


def test_build_history_only_augments_user_turns():
    cid = uuid4()
    user = Message(
        id=uuid4(),
        role="user",
        content="hi",
        created_at=_now(),
        attachments=[_attachment(cid, "doc text")],
    )
    assistant = Message(id=uuid4(), role="assistant", content="hello", created_at=_now())
    history = build_history([user, assistant])
    assert "doc text" in history[0]["content"]
    assert history[1]["content"] == "hello"


# ── upload use case ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_stores_blob_and_extracts_text():
    conv = _conv()
    store = {conv.id: conv}
    attachments: dict = {}
    storage = FakeAttachmentStorage()
    uc = UploadAttachmentUseCase(
        make_uow_factory(store, attachments),
        storage,
        _Extractor("hello world"),
        max_bytes=1024,
    )

    att = await uc.execute(conv.id, USER_ID, "notes.md", "text/markdown", b"hello world")

    assert att.extracted_text == "hello world"
    assert att.message_id is None  # pending
    assert att.s3_key in storage.store
    assert attachments[att.id].id == att.id


@pytest.mark.asyncio
async def test_upload_rejects_oversized():
    conv = _conv()
    uc = UploadAttachmentUseCase(
        make_uow_factory({conv.id: conv}, {}),
        FakeAttachmentStorage(),
        _Extractor(None),
        max_bytes=4,
    )
    with pytest.raises(AttachmentTooLarge):
        await uc.execute(conv.id, USER_ID, "big.bin", "application/octet-stream", b"12345")


@pytest.mark.asyncio
async def test_upload_unknown_conversation_raises():
    uc = UploadAttachmentUseCase(
        make_uow_factory({}, {}), FakeAttachmentStorage(), _Extractor(None), max_bytes=1024
    )
    with pytest.raises(ConversationNotFound):
        await uc.execute(uuid4(), USER_ID, "x.txt", "text/plain", b"x")


# ── send links + injects ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_links_attachment_and_injects_into_history():
    conv = _conv()
    store = {conv.id: conv}
    attachments: dict = {}
    att = _attachment(conv.id, "attached body")
    attachments[att.id] = att
    llm = FakeLLM(["ok"])
    uc = SendMessageUseCase(make_uow_factory(store, attachments), llm, SYSTEM_PROMPT)

    await _collect(uc.stream(conv.id, USER_ID, "read this", [att.id]))

    # attachment now linked to the persisted user message
    user_msg = store[conv.id].messages[0]
    assert attachments[att.id].message_id == user_msg.id
    # extracted text made it into the LLM history, not the stored content
    assert user_msg.content == "read this"
    assert llm.last_history is not None
    assert "attached body" in llm.last_history[-1]["content"]


# ── delete wipes blobs ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_conversation_wipes_storage_prefix():
    conv = _conv()
    store = {conv.id: conv}
    attachments: dict = {}
    storage = FakeAttachmentStorage()
    storage.store[f"conversations/{conv.id}/a/x.md"] = b"data"
    storage.store["conversations/other/keep.md"] = b"keep"
    uc = DeleteConversationUseCase(make_uow_factory(store, attachments), storage)

    await uc.execute(conv.id, USER_ID)

    assert conv.id not in store
    assert list(storage.store.keys()) == ["conversations/other/keep.md"]
