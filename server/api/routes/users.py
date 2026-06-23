from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from api.dependencies import get_current_user
from models.user import User

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.get("/search")
async def search_users(
    query: str = "",
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Поиск пользователей по части логина (без учета регистра, исключая себя)"""
    if not query.strip():
        return {"users": []}

    # Ищем пользователей, логин которых содержит query
    stmt = select(User.username).where(
        User.username.like(f"%{query}%")
    ).limit(20)
    
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    # Исключаем самого себя из результатов
    filtered_users = [u for u in users if u != username]
    
    return {"users": filtered_users}


@router.get("/{target_username}/public-key")
async def get_user_public_key(
    target_username: str,
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == target_username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"public_key": user.public_key}
