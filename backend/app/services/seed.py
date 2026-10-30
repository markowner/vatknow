"""默认管理员账号种子。

数据库为空（全新安装）时，自动创建一个默认管理员账号，
避免用户装完后不知道如何第一次登录。已有任何用户则跳过，不会重复创建。
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Space, SpaceMember, User
from app.services.security import hash_password

DEFAULT_ADMIN_EMAIL = "admin@vat.com"
DEFAULT_ADMIN_PASSWORD = "vat123456"
DEFAULT_ADMIN_NAME = "Admin"


def seed_default_admin(db: Session) -> None:
    """若用户表为空，则创建默认管理员账号及其个人空间。"""
    count = db.scalar(select(func.count()).select_from(User)) or 0
    if count > 0:
        return

    user = User(
        email=DEFAULT_ADMIN_EMAIL,
        password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
        name=DEFAULT_ADMIN_NAME,
        is_site_admin=True,
    )
    db.add(user)
    db.flush()

    space = Space(name="我的知识库", kind="personal", created_by=user.id)
    db.add(space)
    db.flush()
    db.add(SpaceMember(space_id=space.id, user_id=user.id, role="owner"))
    db.commit()
