from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Document, ShareLink, Space
from app.schemas.common import PublicPostDetail, PublicPostOut, PublicSpaceOut
from app.services.openapi import filter_public_spec
from app.services.security import verify_password

router = APIRouter(prefix="/public", tags=["public"])


def _public_content(document: Document, endpoint_keys: list[str] | None = None) -> str | None:
    if document.source_type == "openapi" and document.content_md:
        return filter_public_spec(document.content_md, endpoint_keys)
    return document.content_md


def _public_space(db: Session, slug: str) -> Space:
    space = db.scalar(select(Space).where(Space.slug == slug, Space.visibility == "public"))
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公开空间不存在")
    return space


def _excerpt(text: str) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:180]


def _post_filters(space_id):
    return [
        Document.space_id == space_id,
        Document.published.is_(True),
        Document.source_type.in_(("markdown", "web", "pdf", "openapi")),
    ]


@router.get("/spaces/{slug}", response_model=PublicSpaceOut)
def public_space(slug: str, db: Session = Depends(get_db)) -> PublicSpaceOut:
    space = _public_space(db, slug)
    count = db.scalar(select(func.count()).select_from(Document).where(*_post_filters(space.id))) or 0
    return PublicSpaceOut(name=space.name, slug=space.slug or slug, document_count=int(count))


@router.get("/spaces/{slug}/posts")
def public_posts(
    slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    space = _public_space(db, slug)
    filters = _post_filters(space.id)
    total = db.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
    items = db.scalars(
        select(Document)
        .where(*filters)
        .order_by(Document.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            PublicPostOut(
                id=doc.id,
                slug=doc.slug,
                title=doc.title,
                source_type=doc.source_type,
                excerpt=_excerpt(doc.content_text),
                updated_at=doc.updated_at,
            )
            for doc in items
        ],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


@router.get("/spaces/{slug}/posts/{key}", response_model=PublicPostDetail)
def public_post(slug: str, key: str, db: Session = Depends(get_db)) -> PublicPostDetail:
    space = _public_space(db, slug)
    query = select(Document).where(*_post_filters(space.id))
    try:
        doc_id = UUID(key)
        query = query.where(or_(Document.id == doc_id, Document.slug == key))
    except ValueError:
        query = query.where(Document.slug == key)
    document = db.scalar(query)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在或未发布")
    return PublicPostDetail(
        id=document.id,
        slug=document.slug,
        title=document.title,
        source_type=document.source_type,
        excerpt=_excerpt(document.content_text),
        updated_at=document.updated_at,
        content_md=_public_content(document),
        content_text=document.content_text,
    )


def _load_share(db: Session, token: str) -> ShareLink:
    link = db.scalar(select(ShareLink).where(ShareLink.token == token, ShareLink.revoked.is_(False)))
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在或已失效")
    if link.expires_at is not None:
        from datetime import datetime, timezone

        if link.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="分享已过期")
    return link


@router.get("/shares/{token}/meta")
def public_share_meta(token: str, db: Session = Depends(get_db)) -> dict:
    """密码页需要先展示标题，这里只给元信息，不含正文。"""
    link = _load_share(db, token)
    document = db.get(Document, link.document_id) if link.document_id else None
    space = db.get(Space, link.space_id)
    if link.document_id and (document is None or not document.published):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在或未发布")
    return {
        "title": document.title if document else (space.name if space else "分享"),
        "source_type": document.source_type if document else None,
        "need_password": bool(link.password_hash),
        "expires_at": link.expires_at,
    }


@router.get("/shares/{token}")
def public_share(
    token: str,
    password: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    link = _load_share(db, token)
    if link.password_hash and not (password and verify_password(password, link.password_hash)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要分享密码")
    space = db.get(Space, link.space_id)
    if link.document_id:
        document = db.get(Document, link.document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
        if not document.published:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档未发布")
        return {
            "kind": "document",
            "space_name": space.name if space else "",
            "title": document.title,
            "source_type": document.source_type,
            "content_md": _public_content(document, link.endpoint_keys),
            "content_text": document.content_text,
            "need_password": False,
        }
    docs = db.scalars(
        select(Document)
        .where(Document.space_id == link.space_id, Document.published.is_(True))
        .order_by(Document.updated_at.desc())
        .limit(50)
    ).all()
    return {
        "kind": "space",
        "space_name": space.name if space else "",
        "title": space.name if space else "空间",
        "items": [{"id": d.id, "title": d.title, "source_type": d.source_type, "slug": d.slug} for d in docs],
        "need_password": False,
    }
