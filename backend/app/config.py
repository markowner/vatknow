from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://vatknow:vatknow@localhost:5432/vatknow"
    jwt_secret: str = "dev-change-me-please-use-32-chars-min"
    jwt_expire_minutes: int = 10080
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    cors_origins: str = "http://localhost:3000"
    # 是否开放 Swagger API 文档（/docs）。生产环境务必设为 false。
    enable_docs: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
