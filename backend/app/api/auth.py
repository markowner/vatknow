from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Space, SpaceMember, User
from app.schemas.common import LoginIn, PasswordChange, ProfileUpdate, RegisterIn, TokenResponse, UserPublic
from app.services.security import create_access_token, hash_password, verify_password
from app.services.site import ensure_site_admin, should_become_site_admin

router = APIRouter(prefix="/auth", tags=["auth"])


def _token(user: User) -> TokenResponse:
    return TokenResponse(user=UserPublic.model_validate(user), access_token=create_access_token(user.id))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower()
    exists = db.scalar(select(User).where(User.email == email))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=body.name.strip(),
        # 站点里还没有超管时，第一个注册的人接管全站设置。
        is_site_admin=should_become_site_admin(db),
    )
    db.add(user)
    db.flush()
    space = Space(name="我的知识库", kind="personal", created_by=user.id)
    db.add(space)
    db.flush()
    db.add(SpaceMember(space_id=space.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(user)
    return _token(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    # 密码对了也要拦停用账号，否则停用形同虚设。
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")
    return _token(user)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserPublic)
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user.name = body.name.strip()
    if body.email is not None:
        email = body.email.strip().lower()
        # 邮箱是登录名，必须全局唯一，否则两人同名时登录会串。
        taken = db.scalar(select(User).where(User.email == email, User.id != user.id))
        if taken:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已被其他账号使用")
        user.email = email
    db.commit()
    db.refresh(user)
    return user


@router.post("/password")
def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码不正确")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"detail": "密码已更新"}
