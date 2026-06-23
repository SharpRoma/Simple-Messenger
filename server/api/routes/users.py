from fastapi import APIRouter, Depends
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
