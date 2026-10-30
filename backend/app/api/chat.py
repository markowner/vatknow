from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.common import ChatIn, ChatLogListOut, ChatLogOut, ChatOut, HistoryDocRef
from app.services.access import require_role
from app.services.history import list_chat_logs, record_chat
from app.services.rag import answer_question

router = APIRouter(tags=["chat"])


@router.post("/spaces/{space_id}/chat", response_model=ChatOut)
def chat(
    space_id: UUID,
    body: ChatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatOut:
    require_role(db, user, space_id, "viewer")
    result = answer_question(
        db,
        space_id,
        body.question,
        [{"role": m.role, "content": m.content} for m in body.history],
    )
    # 问答历史在问答页能回看，写入失败不影响本次回答。
    record_chat(
        space_id=space_id,
        user_id=user.id,
        question=body.question,
        answer=result["answer"],
        citations=result["citations"],
    )
    return ChatOut.model_validate(result)


@router.get("/spaces/{space_id}/chat-logs", response_model=ChatLogListOut)
def chat_logs(
    space_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="self", pattern="^(self|space)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatLogListOut:
    """默认只看自己的记录；管理员可以切到 space 查看整个空间。"""
    _, member = require_role(db, user, space_id, "viewer")
    is_admin = member.role in {"owner", "admin"}
    if scope == "space" and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有空间管理员可以查看全部记录")
    rows, total = list_chat_logs(
        db,
        space_id=space_id,
        user_id=None if scope == "space" else user.id,
        page=page,
        page_size=page_size,
    )
    names = _user_names(db, {row.user_id for row in rows if row.user_id})
    items = [
        ChatLogOut(
            id=row.id,
            user_id=row.user_id,
            user_name=names.get(row.user_id),
            question=row.question,
            answer=row.answer,
            citations=[HistoryDocRef(**item) for item in (row.citations or [])],
            created_at=row.created_at,
        )
        for row in rows
    ]
    return ChatLogListOut(items=items, total=total, page=page, page_size=page_size, scope=scope)


def _user_names(db: Session, user_ids: set[UUID]) -> dict[UUID, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.name).where(User.id.in_(user_ids))).all()
    return {row[0]: row[1] for row in rows}
