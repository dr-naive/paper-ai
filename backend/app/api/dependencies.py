"""Shared authentication dependencies for API routers."""

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.auth import decode_token
from app.database import AsyncSessionLocal
from app.models.user import User


async def get_current_user_id(
    authorization: str | None = Header(None),
    db: AsyncSession | None = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    payload = decode_token(authorization.removeprefix("Bearer "))
    user_id = payload.get("sub") if payload else None
    if not user_id:
        raise HTTPException(status_code=401, detail="令牌无效")
    if db is not None:
        result = await db.execute(select(User).filter(User.id == str(user_id)))
        user = result.scalars().first()
    else:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).filter(User.id == str(user_id))
            )
            user = result.scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return str(user_id)
