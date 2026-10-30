import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, Space


def slugify(value: str | None, fallback: str = "item") -> str:
    text = (value or fallback or "").strip()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^\w\-]+", "", text, flags=re.UNICODE)
    text = text.strip("-")[:80]
    return text or fallback[:80] or "item"


def unique_space_slug(db: Session, slug: str, exclude_id=None) -> str:
    base = slug
    n = 2
    while True:
        query = select(Space).where(Space.slug == slug)
        if exclude_id is not None:
            query = query.where(Space.id != exclude_id)
        if db.scalar(query) is None:
            return slug
        slug = f"{base[:70]}-{n}"
        n += 1


def unique_document_slug(db: Session, space_id, slug: str, exclude_id=None) -> str:
    base = slug
    n = 2
    while True:
        query = select(Document).where(Document.space_id == space_id, Document.slug == slug)
        if exclude_id is not None:
            query = query.where(Document.id != exclude_id)
        if db.scalar(query) is None:
            return slug
        slug = f"{base[:140]}-{n}"
        n += 1
