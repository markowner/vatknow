import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    # 前端据此决定是否显示「站点设置」入口。
    is_site_admin: bool = False

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    user: UserPublic
    access_token: str
    token_type: str = "bearer"


def _email(value: str) -> str:
    text = value.strip().lower()
    if "@" not in text or " " in text or text.startswith("@") or text.endswith("@"):
        raise ValueError("请输入邮箱，例如 demo@example.com")
    return text


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _email(value)


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _email(value)


class SpaceOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    role: str
    visibility: str = "private"
    slug: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    visibility: str = Field(default="private", pattern="^(private|public)$")
    slug: str | None = Field(default=None, max_length=80)


class SpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    visibility: str | None = Field(default=None, pattern="^(private|public)$")
    slug: str | None = Field(default=None, max_length=80)


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: str


class MemberCreate(BaseModel):
    email: str
    role: str = Field(pattern="^(admin|editor|viewer)$")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _email(value)


class MemberUpdate(BaseModel):
    role: str = Field(pattern="^(owner|admin|editor|viewer)$")


class DocumentOut(BaseModel):
    id: uuid.UUID
    space_id: uuid.UUID
    title: str
    source_type: str
    slug: str | None = None
    parent_id: uuid.UUID | None = None
    is_folder: bool = False
    published: bool = True
    mime: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    api_summary: str | None = None
    endpoint_count: int | None = None
    api_version: str | None = None
    api_server: str | None = None

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentOut):
    content_text: str
    content_md: str | None


class MarkdownCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content_md: str = ""
    slug: str | None = Field(default=None, max_length=160)
    published: bool = True
    parent_id: uuid.UUID | None = None
    is_folder: bool = False


class MarkdownUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content_md: str | None = None
    slug: str | None = Field(default=None, max_length=160)
    published: bool | None = None
    parent_id: uuid.UUID | None = None
    is_folder: bool | None = None
    # parent_id=None 是合法值（移到顶层），需要显式标记才生效。
    move_parent: bool = False


class FolderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    parent_id: uuid.UUID | None = None


class OpenApiIn(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    spec: str = Field(min_length=2)
    slug: str | None = Field(default=None, max_length=160)
    published: bool = True


class ShareCreate(BaseModel):
    document_id: uuid.UUID | None = None
    password: str | None = Field(default=None, max_length=72)
    expires_days: int | None = Field(default=None, ge=1, le=365)
    # 空表示分享全部已完成接口；给定则只暴露这些 "GET /path" 键。
    endpoint_keys: list[str] | None = Field(default=None, max_length=200)


class ShareUpdate(BaseModel):
    password: str | None = Field(default=None, max_length=72)
    clear_password: bool = False
    expires_days: int | None = Field(default=None, ge=1, le=365)
    clear_expiry: bool = False
    endpoint_keys: list[str] | None = Field(default=None, max_length=200)
    clear_endpoint_keys: bool = False


class ShareOut(BaseModel):
    id: uuid.UUID
    token: str
    document_id: uuid.UUID | None
    has_password: bool
    expires_at: datetime | None
    revoked: bool
    created_at: datetime
    url: str
    endpoint_keys: list[str] | None = None

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    space_id: uuid.UUID | None
    action: str
    method: str
    path: str
    status_code: int
    ip: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


class PublicSpaceOut(BaseModel):
    name: str
    slug: str
    document_count: int


class PublicPostOut(BaseModel):
    id: uuid.UUID
    slug: str | None
    title: str
    source_type: str
    excerpt: str
    updated_at: datetime


class PublicPostDetail(PublicPostOut):
    content_md: str | None
    content_text: str


class PasteIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    html: str | None = None
    text: str | None = None


class SearchHit(BaseModel):
    document_id: uuid.UUID
    document_title: str
    chunk_id: uuid.UUID
    content: str
    score: float
    # 前端据此决定点开哪个页面：API 文档要进接口工作台，而不是普通文档页。
    source_type: str | None = None
    # 跨空间检索时用来标注来源，也决定点开后跳哪个空间。
    space_id: uuid.UUID | None = None
    space_name: str | None = None


class SearchOut(BaseModel):
    items: list[SearchHit]


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)


class Citation(BaseModel):
    document_id: uuid.UUID
    document_title: str
    chunk_id: uuid.UUID
    snippet: str


class ChatOut(BaseModel):
    answer: str
    citations: list[Citation]


class HistoryDocRef(BaseModel):
    """历史记录里的文档引用快照，文档被删除后仍能显示当时的标题。"""

    document_id: uuid.UUID
    document_title: str


class SearchLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    user_name: str | None = None
    query: str
    hit_count: int
    hits: list[HistoryDocRef] = Field(default_factory=list)
    created_at: datetime


class ChatLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    user_name: str | None = None
    question: str
    answer: str
    citations: list[HistoryDocRef] = Field(default_factory=list)
    created_at: datetime


class SearchLogListOut(BaseModel):
    items: list[SearchLogOut]
    total: int
    page: int
    page_size: int
    # true 表示当前用户是管理员、看到的是整个空间的记录。
    scope: str = "self"


class ChatLogListOut(BaseModel):
    items: list[ChatLogOut]
    total: int
    page: int
    page_size: int
    scope: str = "self"


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # 邮箱可选：不传就只改名称，避免老前端调不通。
    email: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return None if value is None else _email(value)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)


class UrlIngest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    title: str | None = Field(default=None, max_length=500)


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class SpaceStats(BaseModel):
    document_count: int
    member_count: int
    chunk_count: int
    by_source: dict[str, int]


class SiteBrandOut(BaseModel):
    """品牌信息，公开读：登录页在未认证时也要显示站名和 Logo。"""

    site_name: str
    site_tagline: str
    # 没有上传过 Logo 时为空，前端回落到内置默认图标。
    has_logo: bool
    logo_version: int
    is_site_admin: bool = False


class SiteBrandUpdate(BaseModel):
    site_name: str | None = Field(default=None, min_length=1, max_length=80)
    site_tagline: str | None = Field(default=None, max_length=120)


class LLMSettingsOut(BaseModel):
    """模型配置。绝不回传完整 API Key，只给尾号和是否已配置。"""

    base_url: str
    model: str
    # 形如 "sk-…3f9a"，够用户确认是不是自己想的那把钥匙。
    api_key_hint: str
    has_api_key: bool
    # Key 是从 .env 来的还是设置页填的，排查问题时有用。
    api_key_source: str
    embedding_model: str
    embedding_dim: int


class LLMSettingsUpdate(BaseModel):
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    # 显式传 null 表示「清除设置页的 Key，回退到 .env」。
    api_key: str | None = Field(default=None, max_length=500)
    clear_api_key: bool = False


class UserSpaceRef(BaseModel):
    """用户管理里展示「这个人属于哪些空间」，比只给 id 更直观。"""

    id: uuid.UUID
    name: str
    kind: str
    role: str


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    is_site_admin: bool
    is_active: bool
    # 个人空间不给「退出」；这里只用来展示归属。
    space_count: int
    spaces: list[UserSpaceRef]


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = None
    is_site_admin: bool | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return None if value is None else _email(value)


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=72)
