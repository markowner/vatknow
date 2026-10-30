"""站点级用户管理。

只有站点管理员能进。这里的操作会直接影响别人能否登录，
所以每个「会导致没人能管站」的动作都要拦下来：
不能停用自己、不能取消自己最后一个超管身份。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Space, SpaceMember, User
from app.schemas.common import (
    AdminPasswordReset,
    AdminUserOut,
    AdminUserUpdate,
    UserSpaceRef,
)
from app.services.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _require_site_admin(user: User) -> None:
    if not user.is_site_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有站点管理员可以管理用户")


def _active_admin_count(db: Session, exclude_id: UUID | None = None) -> int:
    """算还剩下几个「能管站」的人：既要超管，也不能是停用状态。"""
    stmt = select(User.id).where(User.is_site_admin.is_(True), User.is_active.is_(True))
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return len(db.scalars(stmt).all())


def _to_out(db: Session, user: User) -> AdminUserOut:
    rows = db.execute(
        select(Space, SpaceMember.role)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(SpaceMember.user_id == user.id)
        .order_by(Space.created_at.asc())
    ).all()
    spaces = [UserSpaceRef(id=s.id, name=s.name, kind=s.kind, role=role) for s, role in rows]
    return AdminUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        is_site_admin=user.is_site_admin,
        is_active=user.is_active,
        space_count=len(spaces),
        spaces=spaces,
    )


@router.get("", response_model=list[AdminUserOut])
def list_users(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AdminUserOut]:
    _require_site_admin(user)
    users = db.scalars(select(User).order_by(User.created_at.asc())).all()
    return [_to_out(db, u) for u in users]


@router.patch("/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: UUID,
    body: AdminUserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    _require_site_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if body.email is not None:
        email = body.email.strip().lower()
        taken = db.scalar(select(User).where(User.email == email, User.id != target.id))
        if taken:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已被其他账号使用")
        target.email = email

    if body.name is not None:
        target.name = body.name.strip()

    # 降权、停用都要保证「之后还有人能管站」，否则全站设置就再也改不了。
    if body.is_site_admin is not None and body.is_site_admin != target.is_site_admin:
        if not body.is_site_admin and target.is_site_admin and _active_admin_count(db, exclude_id=target.id) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少要保留一个可用的站点管理员",
            )
        target.is_site_admin = body.is_site_admin

    if body.is_active is not None and body.is_active != target.is_active:
        if not body.is_active:
            if target.id == user.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用自己的账号")
            if target.is_site_admin and _active_admin_count(db, exclude_id=target.id) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="至少要保留一个可用的站点管理员",
                )
        target.is_active = body.is_active

    db.commit()
    db.refresh(target)
    return _to_out(db, target)


@router.post("/{user_id}/password")
def reset_password(
    user_id: UUID,
    body: AdminPasswordReset,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """用户忘记密码时唯一的补救手段，系统没有邮件找回。"""
    _require_site_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    target.password_hash = hash_password(body.new_password)
    db.commit()
    return {"detail": "密码已重置"}
