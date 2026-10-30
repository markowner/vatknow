"""检索 / 问答历史记录。

写入走独立的 Session：这两个接口是只读语义（GET 检索、POST 问答），
即使记录失败也不能影响用户拿到结果，所以和审计日志一样把异常吞掉。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ChatLog, SearchLog


def _write(model, **fields) -> None:
    db = SessionLocal()
    try:
        db.add(model(**fields))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def record_search(
    *,
    space_id: UUID | None,
    user_id: UUID,
    query: str,
    hits: list[dict],
) -> None:
    """只存文档标题和 id，正文可能很长且已能在文档里看到。

    space_id 为空表示「全部空间」里的跨库检索。
    """
    snapshot = [
        {
            "document_id": str(hit["document_id"]),
            "document_title": hit["document_title"],
        }
        for hit in hits
    ]
    _write(
        SearchLog,
        space_id=space_id,
        user_id=user_id,
        query=query,
        hit_count=len(hits),
        hits=snapshot,
    )


def record_chat(
    *,
    space_id: UUID,
    user_id: UUID,
    question: str,
    answer: str,
    citations: list[dict],
) -> None:
    snapshot = [
        {
            "document_id": str(item["document_id"]),
            "document_title": item["document_title"],
        }
        for item in citations
    ]
    _write(
        ChatLog,
        space_id=space_id,
        user_id=user_id,
        question=question,
        answer=answer,
        citations=snapshot,
    )


def list_search_logs(
    db: Session,
    *,
    space_id: UUID | None,
    user_id: UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[SearchLog], int]:
    """user_id 为 None 表示管理员查看整个空间。

    space_id 为 None 表示只取「全部空间」的跨库检索记录。
    """
    filters = [SearchLog.space_id.is_(None) if space_id is None else SearchLog.space_id == space_id]
    if user_id is not None:
        filters.append(SearchLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(SearchLog).where(*filters)) or 0
    items = db.scalars(
        select(SearchLog)
        .where(*filters)
        .order_by(SearchLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), int(total)


def list_chat_logs(
    db: Session,
    *,
    space_id: UUID,
    user_id: UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[ChatLog], int]:
    filters = [ChatLog.space_id == space_id]
    if user_id is not None:
        filters.append(ChatLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(ChatLog).where(*filters)) or 0
    items = db.scalars(
        select(ChatLog)
        .where(*filters)
        .order_by(ChatLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), int(total)
