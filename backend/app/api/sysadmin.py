"""
Sysadmin API — управление всеми тенантами (заводами).

Доступно только для роли 'sysadmin'.
Все эндпоинты работают без фильтрации по tenant_id.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.db.models import SafetyCheck, Tenant, User

log = logging.getLogger("firstshift.sysadmin")
router = APIRouter()

_require_sysadmin = require_role("sysadmin")


# ── Схемы ────────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_\-]+$")


class TenantUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


# ── Хелперы ──────────────────────────────────────────────────────────────────

def _tenant_stats(db: Session, tenant: Tenant) -> dict:
    user_count = db.query(func.count(User.id)).filter(User.tenant_id == tenant.id).scalar() or 0
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    safety_today = (
        db.query(func.count(SafetyCheck.id))
        .join(User, SafetyCheck.user_id == User.id)
        .filter(User.tenant_id == tenant.id, SafetyCheck.timestamp >= today_start)
        .scalar() or 0
    )
    return {
        "id":           tenant.id,
        "name":         tenant.name,
        "slug":         tenant.slug,
        "created_at":   tenant.created_at.isoformat(),
        "user_count":   user_count,
        "safety_today": safety_today,
    }


# ── Эндпоинты: тенанты ───────────────────────────────────────────────────────

@router.get("/tenants", summary="Список всех тенантов")
def list_tenants(
    db:  Session = Depends(get_db),
    _:   User    = Depends(_require_sysadmin),
):
    tenants = (
        db.query(Tenant)
        .filter(Tenant.slug != "__system__")
        .order_by(Tenant.created_at.desc())
        .all()
    )
    return [_tenant_stats(db, t) for t in tenants]


@router.post("/tenants", status_code=201, summary="Создать тенант")
def create_tenant(
    body: TenantCreate,
    db:   Session = Depends(get_db),
    _:    User    = Depends(_require_sysadmin),
):
    if db.query(Tenant).filter(Tenant.slug == body.slug).first():
        raise HTTPException(400, f"Тенант '{body.slug}' уже существует")
    tenant = Tenant(name=body.name, slug=body.slug)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    log.info("Создан тенант: %s (id=%d)", tenant.slug, tenant.id)
    return _tenant_stats(db, tenant)


@router.patch("/tenants/{tenant_id}", summary="Переименовать тенант")
def update_tenant(
    tenant_id: int,
    body: TenantUpdate,
    db:   Session = Depends(get_db),
    _:    User    = Depends(_require_sysadmin),
):
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id, Tenant.slug != "__system__"
    ).first()
    if not tenant:
        raise HTTPException(404, "Тенант не найден")
    tenant.name = body.name
    db.commit()
    return _tenant_stats(db, tenant)


@router.delete("/tenants/{tenant_id}", status_code=204, summary="Удалить тенант")
def delete_tenant(
    tenant_id: int,
    db:   Session = Depends(get_db),
    _:    User    = Depends(_require_sysadmin),
):
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id, Tenant.slug != "__system__"
    ).first()
    if not tenant:
        raise HTTPException(404, "Тенант не найден")
    user_count = db.query(func.count(User.id)).filter(User.tenant_id == tenant_id).scalar() or 0
    if user_count > 0:
        raise HTTPException(400, f"Нельзя удалить тенант с {user_count} пользователями")
    db.delete(tenant)
    db.commit()


# ── Эндпоинты: пользователи тенанта ──────────────────────────────────────────

@router.get("/tenants/{tenant_id}/users", summary="Пользователи тенанта")
def list_tenant_users(
    tenant_id: int,
    db:   Session = Depends(get_db),
    _:    User    = Depends(_require_sysadmin),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Тенант не найден")
    users = db.query(User).filter(User.tenant_id == tenant_id).order_by(User.created_at).all()
    return [
        {
            "id":             u.id,
            "username":       u.username,
            "display_name":   u.display_name,
            "role":           u.role,
            "level":          u.level,
            "total_xp":       u.total_xp,
            "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
        }
        for u in users
    ]


# ── Эндпоинт: текущий сисадмин ────────────────────────────────────────────────

@router.get("/me", summary="Профиль sysadmin")
def sysadmin_me(current: User = Depends(_require_sysadmin)):
    return {
        "id":           current.id,
        "username":     current.username,
        "display_name": current.display_name,
        "role":         current.role,
    }
