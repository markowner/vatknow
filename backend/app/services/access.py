from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Space, SpaceMember, User

ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}


def get_membership(db: Session, user_id: UUID, space_id: UUID) -> SpaceMember | None:
    return db.scalar(
        select(SpaceMember).where(SpaceMember.user_id == user_id, SpaceMember.space_id == space_id)
    )


def require_space(db: Session, space_id: UUID) -> Space:
    space = db.get(Space, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间不存在")
    return space


def require_role(db: Session, user: User, space_id: UUID, min_role: str) -> tuple[Space, SpaceMember]:
    space = require_space(db, space_id)
    member = get_membership(db, user.id, space_id)
    if member is None or ROLE_RANK.get(member.role, 0) < ROLE_RANK[min_role]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限执行该操作")
    return space, member


def owner_count(db: Session, space_id: UUID) -> int:
    members = db.scalars(select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.role == "owner")).all()
    return len(members)
