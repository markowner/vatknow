"""全站品牌设置。

只有一行数据（id=1）。读的时候如果还没有就建默认行，
保证调用方拿到的永远是完整对象，不用在接口里到处判空。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SiteSetting, User

DEFAULT_NAME = "VatKnow"
DEFAULT_TAGLINE = "Docs · API"

# 上传的 Logo 限制：SVG 是矢量、体积小，PNG/WebP 覆盖位图场景。
ALLOWED_LOGO_MIME = {"image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/gif"}
MAX_LOGO_BYTES = 512 * 1024


def get_settings(db: Session) -> SiteSetting:
    row = db.get(SiteSetting, 1)
    if row is None:
        row = SiteSetting(id=1, site_name=DEFAULT_NAME, site_tagline=DEFAULT_TAGLINE)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def update_settings(
    db: Session,
    *,
    site_name: str | None = None,
    site_tagline: str | None = None,
) -> SiteSetting:
    row = get_settings(db)
    if site_name is not None:
        row.site_name = site_name.strip()
    if site_tagline is not None:
        row.site_tagline = site_tagline.strip()
    db.commit()
    db.refresh(row)
    return row


def set_logo(db: Session, data: bytes, mime: str) -> SiteSetting:
    row = get_settings(db)
    row.logo_blob = data
    row.logo_mime = mime
    # 版本号用来让浏览器缓存失效，否则换了图前端还是看到旧的。
    row.logo_version = (row.logo_version or 0) + 1
    db.commit()
    db.refresh(row)
    return row


def clear_logo(db: Session) -> SiteSetting:
    row = get_settings(db)
    row.logo_blob = None
    row.logo_mime = None
    row.logo_version = (row.logo_version or 0) + 1
    db.commit()
    db.refresh(row)
    return row


def should_become_site_admin(db: Session) -> bool:
    """还没有任何站点管理员时，让当前这个人补位。

    只判断「是否存在超管」，所以第一人拿到权限，之后注册的人不会自动提权。
    已有历史数据的老库第一次走到这里时，也会把最早注册的账号提上来，
    否则全站设置就没人能改了。
    """
    exists = db.scalar(select(User.id).where(User.is_site_admin.is_(True)).limit(1))
    return exists is None


def ensure_site_admin(db: Session) -> None:
    """老库没有超管时，把最早注册的账号补成站点管理员。"""
    if not should_become_site_admin(db):
        return
    first = db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if first is not None:
        first.is_site_admin = True
        db.commit()


def mask_key(key: str) -> str:
    """只露出尾号，够认出是哪把钥匙，又不会泄露。"""
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "…" + key[-2:]
    return f"{key[:3]}…{key[-4:]}"
