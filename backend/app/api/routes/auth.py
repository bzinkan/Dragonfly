"""Authenticated user routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.auth import CurrentUser, CurrentUserDep

router = APIRouter(prefix="/v1", tags=["auth"])


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUserDep) -> CurrentUser:
    return current_user
