from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.services import llm


def _fts_and_like(db: Session, space_ids: list[UUID], query: str, limit: int) -> list[dict]:
    like = f"%{query.replace('%', '').replace('_', '')}%"
    sql = text(
        """
    SELECT c.id AS chunk_id,
           c.document_id,
           d.title AS document_title,
           d.source_type,
           d.space_id,
           s.name AS space_name,
           c.content,
           0.35 AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    JOIN spaces s ON s.id = c.space_id
    WHERE c.space_id IN :sids
      AND (c.content ILIKE :like OR d.title ILIKE :like)
    ORDER BY c.ordinal ASC
    LIMIT :lim
    """
    ).bindparams(bindparam("sids", expanding=True))
    rows = db.execute(
        sql,
        {"like": like, "sids": [str(sid) for sid in space_ids], "lim": limit},
    ).mappings().all()
    return [dict(row) for row in rows]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _vector(db: Session, space_ids: list[UUID], embedding: list[float], limit: int) -> list[dict]:
    sql = text(
        """
    SELECT c.id AS chunk_id,
           c.document_id,
           d.title AS document_title,
           d.source_type,
           d.space_id,
           s.name AS space_name,
           c.content,
           c.embedding
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    JOIN spaces s ON s.id = c.space_id
    WHERE c.space_id IN :sids
      AND c.embedding IS NOT NULL
    """
    ).bindparams(bindparam("sids", expanding=True))
    rows = db.execute(sql, {"sids": [str(sid) for sid in space_ids]}).mappings().all()
    scored = []
    for row in rows:
        vec = row["embedding"]
        if not isinstance(vec, list):
            continue
        scored.append(
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "document_title": row["document_title"],
                "source_type": row["source_type"],
                "space_id": row["space_id"],
                "space_name": row["space_name"],
                "content": row["content"],
                "score": _cosine(embedding, vec),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def _rrf(left: list[dict], right: list[dict], limit: int, k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    meta: dict[str, dict] = {}
    for rank, hit in enumerate(left, start=1):
        key = str(hit["chunk_id"])
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        meta[key] = hit
    for rank, hit in enumerate(right, start=1):
        key = str(hit["chunk_id"])
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        meta[key] = hit
    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)[:limit]
    results = []
    for key in ordered:
        item = dict(meta[key])
        item["score"] = round(scores[key], 6)
        results.append(item)
    return results


def hybrid_search(db: Session, space_id: UUID, query: str, limit: int = 10) -> list[dict]:
    return hybrid_search_multi(db, [space_id], query, limit)


def hybrid_search_multi(db: Session, space_ids: list[UUID], query: str, limit: int = 10) -> list[dict]:
    """在若干空间内做关键词 + 向量混合检索。

    space_ids 由调用方负责鉴权后传入：单空间检索传一个，跨库检索传用户可见的那些。
    """
    if not space_ids:
        return []
    keyword_hits = _fts_and_like(db, space_ids, query, max(limit, 20))
    vector_hits: list[dict] = []
    # 用 configured(db) 而不是只读 .env 的 llm_configured()：
    # 用户在设置里填了 Key 但 .env 没填时，向量检索也要能生效。
    if llm.configured(db):
        try:
            embedding = llm.embed_texts([query], db=db)[0]
            vector_hits = _vector(db, space_ids, embedding, max(limit, 20))
        except Exception:
            vector_hits = []
    if vector_hits:
        return _rrf(keyword_hits, vector_hits, limit)
    for hit in keyword_hits[:limit]:
        hit["score"] = float(hit["score"] or 0)
    return keyword_hits[:limit]
