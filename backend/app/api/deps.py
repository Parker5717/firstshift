"""
FastAPI dependencies.

get_current_user  — декодирует JWT, возвращает User из БД
require_role      — фабрика dependency для проверки роли
"""

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import User

log = logging.getLogger("firstshift.deps")
settings = get_settings()

_bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Валидировать JWT и вернуть текущего пользователя."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
        tenant_id: int | None = payload.get("tid")
        if user_id is None:
            raise ValueError("sub missing")
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или истёкший токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = db.query(User).filter(User.id == int(user_id))
    if tenant_id is not None:
        query = query.filter(User.tenant_id == tenant_id)
    user = query.first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_tenant_id(current_user: User = Depends(get_current_user)) -> int:
    return current_user.tenant_id


def require_role(*roles: str):
    """
    Фабрика dependency для защиты эндпоинтов по роли.

    Использование:
        @router.get("/admin/users")
        def list_users(user=Depends(require_role("hr", "admin"))):
            ...
    """
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Доступ запрещён. Требуется роль: {', '.join(roles)}",
            )
        return user
    return _check
