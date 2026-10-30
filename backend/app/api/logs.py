from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import AuditLog, User
from app.schemas.common import AuditLogListOut
from app.services.access import require_role

router = APIRouter(tags=["logs"])


@router.get("/spaces/{space_id}/logs", response_model=AuditLogListOut)
def space_logs(
    space_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogListOut:
    require_role(db, user, space_id, "admin")
    filters = [AuditLog.space_id == space_id]
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    items = db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AuditLogListOut(items=list(items), total=int(total), page=page, page_size=page_size)
