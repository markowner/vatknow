from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for stmt in (
            "ALTER TABLE spaces ADD COLUMN IF NOT EXISTS visibility VARCHAR(32) NOT NULL DEFAULT 'private'",
            "ALTER TABLE spaces ADD COLUMN IF NOT EXISTS slug VARCHAR(80)",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS slug VARCHAR(160)",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS published BOOLEAN NOT NULL DEFAULT true",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_spaces_slug ON spaces (slug) WHERE slug IS NOT NULL",
            "ALTER TABLE share_links ADD COLUMN IF NOT EXISTS endpoint_keys JSONB",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES documents(id) ON DELETE SET NULL",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_folder BOOLEAN NOT NULL DEFAULT false",
            "CREATE INDEX IF NOT EXISTS documents_parent_id_idx ON documents (parent_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_space_slug ON documents (space_id, slug) WHERE slug IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS chunks_space_id_idx ON chunks (space_id)",
            "CREATE INDEX IF NOT EXISTS documents_space_id_idx ON documents (space_id)",
            "CREATE INDEX IF NOT EXISTS audit_logs_created_at_idx ON audit_logs (created_at)",
            "CREATE INDEX IF NOT EXISTS search_logs_space_created_idx ON search_logs (space_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS search_logs_user_created_idx ON search_logs (user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS chat_logs_space_created_idx ON chat_logs (space_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS chat_logs_user_created_idx ON chat_logs (user_id, created_at DESC)",
            # 跨空间检索没有归属空间，space_id 需要可为空。
            "ALTER TABLE search_logs ALTER COLUMN space_id DROP NOT NULL",
            "CREATE INDEX IF NOT EXISTS search_logs_global_user_created_idx ON search_logs (user_id, created_at DESC) WHERE space_id IS NULL",
            # 站点管理员：老库加列，并把最早注册的账号补成超管。
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_site_admin BOOLEAN NOT NULL DEFAULT false",
            # 停用账号：登录时校验，默认全部启用，老数据不受影响。
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
            # 模型配置覆盖列：为空表示沿用 .env。
            "ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS llm_base_url VARCHAR(500)",
            "ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS llm_api_key VARCHAR(500)",
            "ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS llm_model VARCHAR(200)",
        ):
            conn.execute(text(stmt))
        conn.commit()

    # 建表和补列都完成后，再处理「一个超管都没有」的情况。
    from app.services.site import ensure_site_admin
    from app.services.seed import seed_default_admin

    session = SessionLocal()
    try:
        seed_default_admin(session)
        ensure_site_admin(session)
    finally:
        session.close()
