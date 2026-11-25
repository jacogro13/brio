from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response, StreamingResponse

from chatbot.domain.conversation.model import Attachment, Conversation
from chatbot.entrypoints.dependencies import (
    get_create_use_case,
    get_current_language,
    get_current_user,
    get_delete_use_case,
    get_download_attachment_use_case,
    get_edit_use_case,
    get_get_use_case,
    get_list_use_case,
    get_regenerate_use_case,
    get_send_message_use_case,
    get_update_use_case,
    get_upload_attachment_use_case,
)
from chatbot.entrypoints.routers.sse import sse_stream
from chatbot.entrypoints.schemas import (
    AttachmentResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    EditMessageRequest,
    MessageResponse,
    RegenerateRequest,
    SendMessageRequest,
    UpdateConversationRequest,
)
from chatbot.services.conversation.create_conversation import CreateConversationUseCase
from chatbot.services.conversation.delete_conversation import DeleteConversationUseCase
from chatbot.services.conversation.download_attachment import DownloadAttachmentUseCase
from chatbot.services.conversation.edit_message import EditMessageUseCase
from chatbot.services.conversation.get_conversation import GetConversationUseCase
from chatbot.services.conversation.list_conversations import ListConversationsUseCase
from chatbot.services.conversation.regenerate_message import RegenerateMessageUseCase
from chatbot.services.conversation.send_message import SendMessageUseCase
from chatbot.services.conversation.update_conversation import UpdateConversationUseCase
from chatbot.services.conversation.upload_attachment import UploadAttachmentUseCase

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Regenerate accepts an empty body; never mutated.
_NO_REGENERATE_OPTIONS = RegenerateRequest()


def _attachment_to_response(a: Attachment) -> AttachmentResponse:
    return AttachmentResponse(
        id=a.id,
        filename=a.filename,
        content_type=a.content_type,
        size=a.size,
        has_text=a.extracted_text is not None,
        created_at=a.created_at,
    )


def _to_response(conv: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                thinking=m.thinking,
                created_at=m.created_at,
                attachments=[_attachment_to_response(a) for a in m.attachments],
                tool_events=(
                    None if m.tool_events is None else [e.to_json() for e in m.tool_events]
                ),
            )
            for m in conv.messages
        ],
        created_at=conv.created_at,
        temperature=conv.temperature,
        max_tokens=conv.max_tokens,
        system_prompt_override=conv.system_prompt_override,
    )


@router.post("/", response_model=ConversationSummaryResponse, status_code=201)
async def create_conversation(
    use_case: Annotated[CreateConversationUseCase, Depends(get_create_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> ConversationSummaryResponse:
    conv = await use_case.execute(user_id)
    return ConversationSummaryResponse(id=conv.id, title=conv.title, created_at=conv.created_at)


@router.get("/", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    use_case: Annotated[ListConversationsUseCase, Depends(get_list_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> list[ConversationSummaryResponse]:
    convs = await use_case.execute(user_id)
    return [
        ConversationSummaryResponse(id=c.id, title=c.title, created_at=c.created_at) for c in convs
    ]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    use_case: Annotated[GetConversationUseCase, Depends(get_get_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> ConversationResponse:
    conv = await use_case.execute(conversation_id, user_id)
    return _to_response(conv)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    body: UpdateConversationRequest,
    use_case: Annotated[UpdateConversationUseCase, Depends(get_update_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> ConversationResponse:
    conv = await use_case.execute(conversation_id, user_id, body.model_dump(exclude_unset=True))
    return _to_response(conv)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    use_case: Annotated[DeleteConversationUseCase, Depends(get_delete_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> None:
    await use_case.execute(conversation_id, user_id)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    use_case: Annotated[SendMessageUseCase, Depends(get_send_message_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
    language: Annotated[str, Depends(get_current_language)],
) -> StreamingResponse:
    return sse_stream(
        use_case.stream(
            conversation_id,
            user_id,
            body.content,
            body.attachment_ids,
            web_access=body.web_access,
            enable_thinking=body.enable_thinking,
            language=language,
        )
    )


@router.post("/{conversation_id}/messages/regenerate")
async def regenerate_message(
    conversation_id: UUID,
    use_case: Annotated[RegenerateMessageUseCase, Depends(get_regenerate_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
    language: Annotated[str, Depends(get_current_language)],
    body: RegenerateRequest = _NO_REGENERATE_OPTIONS,
) -> StreamingResponse:
    return sse_stream(
        use_case.stream(
            conversation_id,
            user_id,
            enable_thinking=body.enable_thinking,
            language=language,
        )
    )


@router.post("/{conversation_id}/messages/{message_id}/edit")
async def edit_message(
    conversation_id: UUID,
    message_id: UUID,
    body: EditMessageRequest,
    use_case: Annotated[EditMessageUseCase, Depends(get_edit_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
    language: Annotated[str, Depends(get_current_language)],
) -> StreamingResponse:
    return sse_stream(
        use_case.stream(
            conversation_id,
            user_id,
            message_id,
            body.content,
            enable_thinking=body.enable_thinking,
            language=language,
        )
    )


@router.post(
    "/{conversation_id}/attachments",
    response_model=AttachmentResponse,
    status_code=201,
)
async def upload_attachment(
    conversation_id: UUID,
    file: Annotated[UploadFile, File(...)],
    use_case: Annotated[UploadAttachmentUseCase, Depends(get_upload_attachment_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> AttachmentResponse:
    data = await file.read()
    attachment = await use_case.execute(
        conversation_id,
        user_id,
        filename=file.filename or "attachment",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return _attachment_to_response(attachment)


@router.get("/{conversation_id}/attachments/{attachment_id}")
async def download_attachment(
    conversation_id: UUID,
    attachment_id: UUID,
    use_case: Annotated[DownloadAttachmentUseCase, Depends(get_download_attachment_use_case)],
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> Response:
    attachment, data = await use_case.execute(conversation_id, user_id, attachment_id)
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )
