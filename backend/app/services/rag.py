from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services import llm
from app.services.search import hybrid_search

SYSTEM_PROMPT = """你是 VatKnow 知识库助手。只根据「资料」中的内容回答用户问题。
规则：
1. 若资料不足以回答，直接说明知识库中没有相关内容，不要编造。
2. 使用资料时在句末用 [编号] 标注来源，编号与资料条目一致。
3. 回答简洁、准确，使用与用户相同的语言。"""


def answer_question(db: Session, space_id: UUID, question: str, history: list[dict]) -> dict:
    if not llm.configured(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置模型 API Key，无法进行智能问答。请在账号设置里填写。",
        )
    hits = hybrid_search(db, space_id, question, limit=8)
    if not hits:
        return {
            "answer": "知识库中没有检索到与问题相关的内容。请先在该空间收录文档，或换一种问法。",
            "citations": [],
        }
    numbered = []
    citations = []
    for idx, hit in enumerate(hits, start=1):
        numbered.append(f"[{idx}] 《{hit['document_title']}》\n{hit['content']}")
        snippet = hit["content"]
        if len(snippet) > 240:
            snippet = snippet[:240] + "…"
        citations.append(
            {
                "document_id": hit["document_id"],
                "document_title": hit["document_title"],
                "chunk_id": hit["chunk_id"],
                "snippet": snippet,
            }
        )
    context = "\n\n".join(numbered)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history[-10:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append(
        {
            "role": "user",
            "content": f"资料：\n{context}\n\n问题：{question}",
        }
    )
    try:
        answer = llm.chat_completion(messages, db=db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"调用模型失败：{exc}",
        ) from exc
    return {"answer": answer, "citations": citations}
