from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import SpaceMember, User
from app.schemas.common import HistoryDocRef, SearchHit, SearchLogListOut, SearchLogOut, SearchOut
from app.services.access import require_role
from app.services.history import list_search_logs, record_search
from app.services.search import hybrid_search, hybrid_search_multi

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchOut)
def search_all(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchOut:
    """在当前用户可见的所有空间里检索。

    可见范围严格从 space_members 取，不信任前端传的空间 id，
    否则只要改个参数就能搜到别人的库。
    """
    space_ids = list(
        db.scalars(select(SpaceMember.space_id).where(SpaceMember.user_id == user.id)).all()
    )
    if not space_ids:
        return SearchOut(items=[])
    hits = hybrid_search_multi(db, space_ids, q, limit)
    items = [
        SearchHit(
            document_id=hit["document_id"],
            document_title=hit["document_title"],
            chunk_id=hit["chunk_id"],
            content=hit["content"],
            score=float(hit["score"] or 0),
            source_type=hit.get("source_type"),
            space_id=hit.get("space_id"),
            space_name=hit.get("space_name"),
        )
        for hit in hits
    ]
    # 跨库检索没有单一归属空间，space_id 留空。
    record_search(space_id=None, user_id=user.id, query=q, hits=hits)
    return SearchOut(items=items)


@router.get("/search-logs", response_model=SearchLogListOut)
def search_all_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchLogListOut:
    """「全部空间」页只看自己的跨库检索记录，别人的检索不属于这个页面的语境。"""
    rows, total = list_search_logs(
        db,
        space_id=None,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )
    names = _user_names(db, {row.user_id for row in rows if row.user_id})
    items = [
        SearchLogOut(
            id=row.id,
            user_id=row.user_id,
            user_name=names.get(row.user_id),
            query=row.query,
            hit_count=row.hit_count,
            hits=[HistoryDocRef(**item) for item in (row.hits or [])],
            created_at=row.created_at,
        )
        for row in rows
    ]
    return SearchLogListOut(items=items, total=total, page=page, page_size=page_size, scope="self")


@router.get("/spaces/{space_id}/search", response_model=SearchOut)
def search_space(
    space_id: UUID,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchOut:
    require_role(db, user, space_id, "viewer")
    hits = hybrid_search(db, space_id, q, limit)
    items = [
        SearchHit(
            document_id=hit["document_id"],
            document_title=hit["document_title"],
            chunk_id=hit["chunk_id"],
            content=hit["content"],
            score=float(hit["score"] or 0),
            source_type=hit.get("source_type"),
            space_id=hit.get("space_id") or space_id,
            space_name=hit.get("space_name"),
        )
        for hit in hits
    ]
    # 检索历史用于回看之前搜过什么，写入失败不能影响本次结果。
    record_search(space_id=space_id, user_id=user.id, query=q, hits=hits)
    return SearchOut(items=items)


@router.get("/spaces/{space_id}/search-logs", response_model=SearchLogListOut)
def search_logs(
    space_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="self", pattern="^(self|space)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchLogListOut:
    """默认只看自己的记录；管理员可以切到 space 查看整个空间。"""
    _, member = require_role(db, user, space_id, "viewer")
    is_admin = member.role in {"owner", "admin"}
    if scope == "space" and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有空间管理员可以查看全部记录")
    rows, total = list_search_logs(
        db,
        space_id=space_id,
        user_id=None if scope == "space" else user.id,
        page=page,
        page_size=page_size,
    )
    names = _user_names(db, {row.user_id for row in rows if row.user_id})
    items = [
        SearchLogOut(
            id=row.id,
            user_id=row.user_id,
            user_name=names.get(row.user_id),
            query=row.query,
            hit_count=row.hit_count,
            hits=[HistoryDocRef(**item) for item in (row.hits or [])],
            created_at=row.created_at,
        )
        for row in rows
    ]
    return SearchLogListOut(items=items, total=total, page=page, page_size=page_size, scope=scope)


def _user_names(db: Session, user_ids: set[UUID]) -> dict[UUID, str]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(User.id, User.name).where(User.id.in_(user_ids))
    ).all()
    return {row[0]: row[1] for row in rows}


@router.get("/spaces/{space_id}/docs-search")
def docs_search(
    space_id: UUID,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=12, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """目录树用的轻量全文检索：按文档去重，附带命中片段，便于左栏直接定位。"""
    require_role(db, user, space_id, "viewer")
    like = f"%{q.replace('%', '').replace('_', '')}%"
    rows = db.execute(
        text(
            """
            SELECT d.id,
                   d.title,
                   d.source_type,
                   d.is_folder,
                   d.updated_at,
                   (SELECT c.content
                      FROM chunks c
                     WHERE c.document_id = d.id AND c.content ILIKE :like
                     ORDER BY c.ordinal ASC
                     LIMIT 1) AS snippet,
                   EXISTS (SELECT 1 FROM chunks c WHERE c.document_id = d.id AND c.content ILIKE :like) AS in_body
              FROM documents d
             WHERE d.space_id = :sid
               AND d.is_folder IS FALSE
               AND (d.title ILIKE :like OR EXISTS (
                     SELECT 1 FROM chunks c WHERE c.document_id = d.id AND c.content ILIKE :like))
             ORDER BY in_body DESC, d.updated_at DESC
             LIMIT :lim
            """
        ),
        {"like": like, "sid": str(space_id), "lim": limit},
    ).mappings().all()

    items = []
    for row in rows:
        snippet = (row["snippet"] or "").strip().replace("\n", " ")
        items.append(
            {
                "id": str(row["id"]),
                "title": row["title"],
                "source_type": row["source_type"],
                "snippet": snippet[:160],
                "in_body": bool(row["in_body"]),
            }
        )
    return {"items": items, "total": len(items)}
