"""Shared authentication dependencies for API routers."""

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import decode_token


async def get_current_user_id(
    authorization: str | None = Header(None),
    db: AsyncSession | None = None,
) -> str:
    del db  # Kept in the signature for backwards-compatible callers.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    payload = decode_token(authorization.removeprefix("Bearer "))
    user_id = payload.get("sub") if payload else None
    if not user_id:
        raise HTTPException(status_code=401, detail="令牌无效")
    return str(user_id)
