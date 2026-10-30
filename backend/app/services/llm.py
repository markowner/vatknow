"""模型调用。

配置来源有两层，数据库优先、`.env` 兜底：
- 数据库里的值来自「站点设置」，改完立即生效，不用重启也不用改代码。
- `.env` 里的值作为默认值，所以老部署不填也能照常跑。

对话模型可以换；向量模型（embedding）固定读 `.env`，
因为换向量模型通常意味着维度变化，历史向量会全部失效，
这种操作不适合在界面上顺手点一下。
"""

from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SiteSetting


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key: str
    chat_model: str


def resolve(db: Session | None = None) -> ProviderConfig:
    """把数据库覆盖值和 .env 默认值合成一份可用配置。"""
    row = db.get(SiteSetting, 1) if db is not None else None
    return ProviderConfig(
        base_url=(getattr(row, "llm_base_url", None) or settings.openai_base_url or "").strip(),
        api_key=(getattr(row, "llm_api_key", None) or settings.openai_api_key or "").strip(),
        chat_model=(getattr(row, "llm_model", None) or settings.openai_model or "").strip(),
    )


def llm_configured() -> bool:
    """只看 .env 的配置。向量检索用它判断，保持原有语义。"""
    return bool(settings.openai_api_key.strip())


def configured(db: Session | None = None) -> bool:
    """问答能否调用模型：数据库或 .env 任一处有 Key 即可。"""
    return bool(resolve(db).api_key)


def client(cfg: ProviderConfig | None = None) -> OpenAI:
    cfg = cfg or resolve()
    if not cfg.api_key:
        raise RuntimeError("未配置 API Key，无法调用模型")
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)


def embed_texts(texts: list[str], db: Session | None = None) -> list[list[float]]:
    """向量化。

    Key 和 base_url 走同一份解析结果，站点设置里填一次两边都能用；
    模型名固定读 .env，避免换模型后历史向量维度对不上。
    """
    if not texts:
        return []
    cfg = resolve(db)
    if not cfg.api_key:
        raise RuntimeError("未配置 API Key，无法生成向量")
    api = client(cfg)
    vectors: list[list[float]] = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = api.embeddings.create(model=settings.embedding_model, input=batch)
        ordered = sorted(resp.data, key=lambda item: item.index)
        for item in ordered:
            vec = list(item.embedding)
            if len(vec) != settings.embedding_dim:
                raise RuntimeError(
                    f"向量维度为 {len(vec)}，与 EMBEDDING_DIM={settings.embedding_dim} 不一致"
                )
            vectors.append(vec)
    return vectors


def chat_completion(messages: list[dict[str, str]], db: Session | None = None) -> str:
    cfg = resolve(db)
    api = client(cfg)
    resp = api.chat.completions.create(
        model=cfg.chat_model,
        messages=messages,
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()
