import re
from io import BytesIO
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.services import llm


def extract_pdf(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def html_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title[:500]
    heading = soup.find("h1")
    if heading:
        text = heading.get_text(" ", strip=True)
        if text:
            return text[:500]
    return None


def extract_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text("\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def markdown_to_text(md: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", md)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    return text.strip()


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + size, length)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def rebuild_chunks(db: Session, document: Document) -> None:
    db.execute(delete(Chunk).where(Chunk.document_id == document.id))
    pieces = chunk_text(document.content_text or "")
    embeddings: list[list[float] | None] = [None] * len(pieces)
    if pieces and llm.configured(db):
        try:
            embeddings = llm.embed_texts(pieces, db=db)
        except Exception:
            embeddings = [None] * len(pieces)
    for idx, content in enumerate(pieces):
        chunk = Chunk(
            document_id=document.id,
            space_id=document.space_id,
            ordinal=idx,
            content=content,
            embedding=embeddings[idx] if idx < len(embeddings) else None,
            tsv=func.to_tsvector("simple", content),
        )
        db.add(chunk)


def save_and_index(db: Session, document: Document) -> Document:
    db.add(document)
    db.flush()
    rebuild_chunks(db, document)
    db.commit()
    db.refresh(document)
    return document


def update_markdown(
    db: Session,
    document: Document,
    title: str | None,
    content_md: str | None,
    slug: str | None = None,
    published: bool | None = None,
) -> Document:
    from app.services.openapi import parse_openapi
    from app.services.slugs import slugify, unique_document_slug

    if title is not None:
        document.title = title.strip()
    if published is not None:
        document.published = published
    if slug is not None:
        cleaned = slug.strip()
        document.slug = (
            unique_document_slug(db, document.space_id, slugify(cleaned, document.title), exclude_id=document.id)
            if cleaned
            else None
        )
    if content_md is not None:
        if document.source_type == "markdown":
            document.content_md = content_md
            document.content_text = markdown_to_text(content_md)
            rebuild_chunks(db, document)
        elif document.source_type == "openapi":
            _data, spec_title, stored, text = parse_openapi(content_md)
            document.content_md = stored
            document.content_text = text
            if title is None and spec_title:
                document.title = spec_title
            rebuild_chunks(db, document)
        else:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该类型文档不能修改正文")
    db.commit()
    db.refresh(document)
    return document
