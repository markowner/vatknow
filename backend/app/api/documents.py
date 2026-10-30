from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Chunk, Document, SpaceMember, User
from app.schemas.common import (
    DocumentDetail,
    DocumentListOut,
    DocumentOut,
    FolderCreate,
    MarkdownCreate,
    MarkdownUpdate,
    OpenApiIn,
    PasteIn,
    SpaceStats,
    UrlIngest,
)
from app.services.access import require_role
from app.services.ingest import extract_html, extract_pdf, html_title, markdown_to_text, save_and_index, update_markdown
from app.services.openapi import parse_openapi
from app.services.slugs import slugify, unique_document_slug

router = APIRouter(tags=["documents"])

MAX_PDF_BYTES = 20 * 1024 * 1024


def _get_document(db: Session, document_id: UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return document


def _openapi_meta(document: Document) -> dict:
    """列表页只需要摘要和接口数，避免把整份 OpenAPI 下发给前端。"""
    if document.source_type != "openapi" or not document.content_md:
        return {}
    try:
        import json

        data = json.loads(document.content_md)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    info = data.get("info") or {}
    paths = data.get("paths") or {}
    count = sum(len([m for m in (ops or {}) if m in {"get", "post", "put", "patch", "delete", "head", "options"}]) for ops in paths.values())
    description = str(info.get("description") or "")[:280]
    servers = data.get("servers") or []
    server = ""
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        server = str(servers[0].get("url") or "")[:200]
    return {
        "api_summary": description,
        "endpoint_count": count,
        "api_version": str(info.get("version") or "")[:40],
        "api_server": server,
    }


def _to_out(document: Document) -> DocumentOut:
    out = DocumentOut.model_validate(document)
    for key, value in _openapi_meta(document).items():
        setattr(out, key, value)
    return out


@router.get("/spaces/{space_id}/stats", response_model=SpaceStats)
def space_stats(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpaceStats:
    require_role(db, user, space_id, "viewer")
    # 目录和文档同表存放，只靠 is_folder 区分，统计文档时必须排掉目录。
    not_folder = Document.is_folder.is_(False)
    document_count = (
        db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.space_id == space_id, not_folder)
        )
        or 0
    )
    member_count = db.scalar(select(func.count()).select_from(SpaceMember).where(SpaceMember.space_id == space_id)) or 0
    chunk_count = db.scalar(select(func.count()).select_from(Chunk).where(Chunk.space_id == space_id)) or 0
    rows = db.execute(
        select(Document.source_type, func.count())
        .where(Document.space_id == space_id, not_folder)
        .group_by(Document.source_type)
    ).all()
    by_source = {str(source): int(count) for source, count in rows}
    return SpaceStats(
        document_count=int(document_count),
        member_count=int(member_count),
        chunk_count=int(chunk_count),
        by_source=by_source,
    )


@router.get("/spaces/{space_id}/documents", response_model=DocumentListOut)
def list_documents(
    space_id: UUID,
    q: str | None = None,
    source_type: str | None = Query(default=None),
    is_folder: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentListOut:
    require_role(db, user, space_id, "viewer")
    filters = [Document.space_id == space_id]
    if q:
        filters.append(Document.title.ilike(f"%{q}%"))
    if source_type:
        filters.append(Document.source_type == source_type)
    if is_folder is not None:
        filters.append(Document.is_folder.is_(is_folder))
    total = db.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Document)
            .where(*filters)
            .order_by(Document.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return DocumentListOut(
        items=[_to_out(item) for item in items],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.post("/spaces/{space_id}/documents", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def create_markdown(
    space_id: UUID,
    body: MarkdownCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_role(db, user, space_id, "editor")
    slug = unique_document_slug(db, space_id, slugify(body.slug, body.title)) if body.slug else None
    document = Document(
        space_id=space_id,
        title=body.title.strip(),
        source_type="markdown",
        slug=slug,
        published=body.published,
        content_md=body.content_md,
        content_text=markdown_to_text(body.content_md),
        mime="text/markdown",
        created_by=user.id,
    )
    return save_and_index(db, document)


@router.post(
    "/spaces/{space_id}/documents/upload",
    response_model=DocumentDetail,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pdf(
    space_id: UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_role(db, user, space_id, "editor")
    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PDF 文件")
    data = await file.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PDF 不能超过 20MB")
    text = extract_pdf(data)
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法从 PDF 提取文本")
    document = Document(
        space_id=space_id,
        title=(title or filename).strip(),
        source_type="pdf",
        content_text=text,
        mime="application/pdf",
        created_by=user.id,
    )
    return save_and_index(db, document)


@router.post("/spaces/{space_id}/documents/paste", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def paste_web(
    space_id: UUID,
    body: PasteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_role(db, user, space_id, "editor")
    if body.html:
        text = extract_html(body.html)
    else:
        text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供 html 或 text")
    document = Document(
        space_id=space_id,
        title=body.title.strip(),
        source_type="web",
        content_text=text,
        mime="text/html" if body.html else "text/plain",
        created_by=user.id,
    )
    return save_and_index(db, document)


@router.post("/spaces/{space_id}/documents/from-url", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def ingest_url(
    space_id: UUID,
    body: UrlIngest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_role(db, user, space_id, "editor")
    parsed = urlparse(body.url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入有效的 http(s) 网址")
    try:
        with httpx.Client(follow_redirects=True, timeout=20.0) as client:
            response = client.get(body.url.strip(), headers={"User-Agent": "VatKnow/0.1"})
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"抓取失败：{exc}") from exc
    text = extract_html(html)
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="网页没有可提取的正文")
    title = (body.title or html_title(html) or parsed.netloc).strip()
    document = Document(
        space_id=space_id,
        title=title[:500],
        source_type="web",
        content_text=text,
        mime="text/html",
        created_by=user.id,
    )
    return save_and_index(db, document)


@router.post("/spaces/{space_id}/documents/openapi", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def ingest_openapi(
    space_id: UUID,
    body: OpenApiIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_role(db, user, space_id, "editor")
    _data, spec_title, stored, text = parse_openapi(body.spec)
    title = (body.title or spec_title).strip()
    slug = unique_document_slug(db, space_id, slugify(body.slug, title)) if body.slug or body.published else None
    document = Document(
        space_id=space_id,
        title=title[:500],
        source_type="openapi",
        slug=slug,
        published=body.published,
        content_md=stored,
        content_text=text,
        mime="application/json",
        created_by=user.id,
    )
    return save_and_index(db, document)


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Document:
    document = _get_document(db, document_id)
    require_role(db, user, document.space_id, "viewer")
    return document


@router.patch("/documents/{document_id}", response_model=DocumentDetail)
def patch_document(
    document_id: UUID,
    body: MarkdownUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    document = _get_document(db, document_id)
    require_role(db, user, document.space_id, "editor")
    if body.content_md is not None and document.source_type not in {"markdown", "openapi"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该类型文档不能修改正文")
    updated = update_markdown(db, document, body.title, body.content_md, body.slug, body.published)
    if body.move_parent:
        updated.parent_id = _safe_parent(db, document.space_id, document.id, body.parent_id)
        db.commit()
        db.refresh(updated)
    elif body.parent_id is not None:
        updated.parent_id = _safe_parent(db, document.space_id, document.id, body.parent_id)
        db.commit()
        db.refresh(updated)
    if body.is_folder is not None and body.is_folder != updated.is_folder:
        updated.is_folder = body.is_folder
        db.commit()
        db.refresh(updated)
    return updated


def _safe_parent(db: Session, space_id: UUID, document_id: UUID, parent_id: UUID | None) -> UUID | None:
    """校验父节点：必须同空间、不是自己、也不能是自己的后代，避免目录成环。"""
    if parent_id is None:
        return None
    if parent_id == document_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能把文档移动到它自己下面")
    parent = db.get(Document, parent_id)
    if parent is None or parent.space_id != space_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标目录不存在")
    if not parent.is_folder:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能移动到目录节点下")

    seen: set[UUID] = set()
    cursor: Document | None = parent
    while cursor is not None and cursor.id not in seen:
        if cursor.id == document_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能移动到自己的子目录下")
        seen.add(cursor.id)
        cursor = db.get(Document, cursor.parent_id) if cursor.parent_id else None
    return parent_id


@router.post(
    "/spaces/{space_id}/documents/folders",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_folder(
    space_id: UUID,
    body: FolderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_role(db, user, space_id, "editor")
    folder = Document(
        space_id=space_id,
        title=body.title.strip(),
        source_type="folder",
        is_folder=True,
        content_text="",
        mime=None,
        created_by=user.id,
    )
    db.add(folder)
    db.flush()
    if body.parent_id:
        folder.parent_id = _safe_parent(db, space_id, folder.id, body.parent_id)
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    document = _get_document(db, document_id)
    require_role(db, user, document.space_id, "editor")
    db.delete(document)
    db.commit()
