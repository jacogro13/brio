from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from chatbot.domain.user.model import UserNotFound
from chatbot.domain.user.ports.user_unit_of_work import UserUnitOfWorkFactory
from chatbot.entrypoints.dependencies import (
    get_current_user,
    get_login_use_case,
    get_register_use_case,
    get_user_uow_factory,
)
from chatbot.entrypoints.routers.limiter import limiter
from chatbot.entrypoints.schemas import (
    LoginRequest,
    ProfileResponse,
    RegisterRequest,
    TokenResponse,
    UpdateLanguageRequest,
    UserResponse,
)
from chatbot.entrypoints.settings import get_settings
from chatbot.services.user.login_user import LoginUserUseCase
from chatbot.services.user.register_user import RegisterUserUseCase

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    use_case: Annotated[RegisterUserUseCase, Depends(get_register_use_case)],
) -> UserResponse:
    user = await use_case.execute(body.username, body.password, body.language)
    return UserResponse(id=user.id, username=user.username)


def _login_rate_limit() -> str:
    # slowapi calls the limit-value callable with no args; read the (cached)
    # setting so e2e can override it via LOGIN_RATE_LIMIT.
    return get_settings().login_rate_limit


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_login_rate_limit)
async def login(
    request: Request,
    body: LoginRequest,
    use_case: Annotated[LoginUserUseCase, Depends(get_login_use_case)],
) -> TokenResponse:
    token = await use_case.execute(body.username, body.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=ProfileResponse)
async def get_me(
    user_id: Annotated[UUID, Depends(get_current_user)],
    uow_factory: Annotated[UserUnitOfWorkFactory, Depends(get_user_uow_factory)],
) -> ProfileResponse:
    async with uow_factory() as uow:
        user = await uow.users.get_by_id(user_id)
    if user is None:
        raise UserNotFound(f"user {user_id} not found")
    return ProfileResponse(username=user.username, language=user.language)


@router.patch("/me", response_model=ProfileResponse)
async def update_me(
    body: UpdateLanguageRequest,
    user_id: Annotated[UUID, Depends(get_current_user)],
    uow_factory: Annotated[UserUnitOfWorkFactory, Depends(get_user_uow_factory)],
) -> ProfileResponse:
    async with uow_factory() as uow:
        user = await uow.users.get_by_id(user_id)
        if user is None:
            raise UserNotFound(f"user {user_id} not found")
        await uow.users.set_language(user_id, body.language)
    return ProfileResponse(username=user.username, language=body.language)
