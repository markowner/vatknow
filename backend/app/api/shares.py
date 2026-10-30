import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Document, ShareLink, User
from app.schemas.common import ShareCreate, ShareOut, ShareUpdate
from app.services.access import require_role
from app.services.openapi import done_endpoints, normalize_endpoint_key
from app.services.security import hash_password

router = APIRouter(tags=["shares"])


def _share_url(request: Request, token: str) -> str:
    origin = str(request.base_url).rstrip("/")
    return f"{origin.replace(':8000', ':3000')}/s/{token}"


def _out(link: ShareLink, request: Request) -> ShareOut:
    return ShareOut(
        id=link.id,
        token=link.token,
        document_id=link.document_id,
        has_password=bool(link.password_hash),
        expires_at=link.expires_at,
        revoked=link.revoked,
        created_at=link.created_at,
        url=_share_url(request, link.token),
        endpoint_keys=link.endpoint_keys,
    )


def _normalize_keys(document: Document | None, keys: list[str] | None) -> list[str] | None:
    """白名单只能取文档里真实存在的接口，避免存入无效键导致外部页空白。"""
    if not keys:
        return None
    if document is None or document.source_type != "openapi" or not document.content_md:
        return None
    available = set(done_endpoints(document.content_md))
    picked = [normalize_endpoint_key(key) for key in keys if key.strip()]
    valid = [key for key in dict.fromkeys(picked) if key in available]
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个已完成的接口")
    # 全选等同于不限，省得白名单和「全部」两种状态混在一起。
    return None if len(valid) == len(available) else valid


@router.get("/spaces/{space_id}/shares", response_model=list[ShareOut])
def list_shares(
    space_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShareOut]:
    require_role(db, user, space_id, "viewer")
    rows = db.scalars(
        select(ShareLink)
        .where(ShareLink.space_id == space_id, ShareLink.revoked.is_(False))
        .order_by(ShareLink.created_at.desc())
    ).all()
    return [_out(row, request) for row in rows]


@router.post("/spaces/{space_id}/shares", response_model=ShareOut, status_code=status.HTTP_201_CREATED)
def create_share(
    space_id: UUID,
    body: ShareCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareOut:
    require_role(db, user, space_id, "editor")
    document = None
    if body.document_id:
        document = db.get(Document, body.document_id)
        if document is None or document.space_id != space_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    expires_at = None
    if body.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)
    link = ShareLink(
        token=secrets.token_urlsafe(18),
        space_id=space_id,
        document_id=body.document_id,
        password_hash=hash_password(body.password) if body.password else None,
        expires_at=expires_at,
        endpoint_keys=_normalize_keys(document, body.endpoint_keys),
        created_by=user.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return _out(link, request)


@router.patch("/spaces/{space_id}/shares/{share_id}", response_model=ShareOut)
def update_share(
    space_id: UUID,
    share_id: UUID,
    body: ShareUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareOut:
    require_role(db, user, space_id, "editor")
    link = db.get(ShareLink, share_id)
    if link is None or link.space_id != space_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在")

    if body.clear_password:
        link.password_hash = None
    elif body.password:
        link.password_hash = hash_password(body.password)

    if body.clear_expiry:
        link.expires_at = None
    elif body.expires_days:
        link.expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)

    if body.clear_endpoint_keys:
        link.endpoint_keys = None
    elif body.endpoint_keys is not None:
        document = db.get(Document, link.document_id) if link.document_id else None
        link.endpoint_keys = _normalize_keys(document, body.endpoint_keys)

    db.commit()
    db.refresh(link)
    return _out(link, request)


@router.get("/spaces/{space_id}/shares/{share_id}/endpoints")
def share_endpoints(
    space_id: UUID,
    share_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """返回可选接口清单与当前白名单，供分享设置界面勾选。"""
    require_role(db, user, space_id, "viewer")
    link = db.get(ShareLink, share_id)
    if link is None or link.space_id != space_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在")
    document = db.get(Document, link.document_id) if link.document_id else None
    if document is None or document.source_type != "openapi" or not document.content_md:
        return {"items": [], "selected": []}
    return {
        "items": done_endpoints(document.content_md),
        "selected": link.endpoint_keys or [],
    }


@router.delete("/spaces/{space_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(
    space_id: UUID,
    share_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    require_role(db, user, space_id, "editor")
    link = db.get(ShareLink, share_id)
    if link is None or link.space_id != space_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在")
    link.revoked = True
    db.commit()
