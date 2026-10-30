from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.common import (
    LLMSettingsOut,
    LLMSettingsUpdate,
    SiteBrandOut,
    SiteBrandUpdate,
)
from app.services import llm
from app.services.site import (
    ALLOWED_LOGO_MIME,
    MAX_LOGO_BYTES,
    clear_logo,
    get_settings,
    mask_key,
    set_logo,
    update_settings,
)

router = APIRouter(tags=["site"])


def _require_site_admin(user: User, action: str = "修改") -> None:
    if not user.is_site_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"只有站点管理员可以{action}全站设置",
        )


@router.get("/site/brand", response_model=SiteBrandOut)
def read_brand(db: Session = Depends(get_db)) -> SiteBrandOut:
    """公开接口：登录页在没有 token 时也要显示站名和 Logo。"""
    row = get_settings(db)
    return SiteBrandOut(
        site_name=row.site_name,
        site_tagline=row.site_tagline,
        has_logo=row.logo_blob is not None,
        logo_version=row.logo_version or 0,
        is_site_admin=False,
    )


@router.get("/site/brand/me", response_model=SiteBrandOut)
def read_brand_me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SiteBrandOut:
    """登录后额外带上「我能不能改」，前端据此决定是否显示设置入口。"""
    row = get_settings(db)
    return SiteBrandOut(
        site_name=row.site_name,
        site_tagline=row.site_tagline,
        has_logo=row.logo_blob is not None,
        logo_version=row.logo_version or 0,
        is_site_admin=bool(user.is_site_admin),
    )


@router.get("/site/logo")
def read_logo(db: Session = Depends(get_db)) -> Response:
    """Logo 原图。带上版本号查询参数，换图后浏览器会重新拉。"""
    row = get_settings(db)
    if row.logo_blob is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚未上传 Logo")
    return Response(
        content=row.logo_blob,
        media_type=row.logo_mime or "image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.patch("/site/brand", response_model=SiteBrandOut)
def patch_brand(
    body: SiteBrandUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SiteBrandOut:
    _require_site_admin(user)
    row = update_settings(
        db, site_name=body.site_name, site_tagline=body.site_tagline
    )
    return SiteBrandOut(
        site_name=row.site_name,
        site_tagline=row.site_tagline,
        has_logo=row.logo_blob is not None,
        logo_version=row.logo_version or 0,
        is_site_admin=True,
    )


@router.post("/site/logo", response_model=SiteBrandOut)
async def upload_logo(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SiteBrandOut:
    _require_site_admin(user)
    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_LOGO_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 PNG、JPEG、WebP、GIF 或 SVG 图片",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件为空")
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Logo 不能超过 512KB")
    row = set_logo(db, data, mime)
    return SiteBrandOut(
        site_name=row.site_name,
        site_tagline=row.site_tagline,
        has_logo=True,
        logo_version=row.logo_version or 0,
        is_site_admin=True,
    )


@router.delete("/site/logo", response_model=SiteBrandOut)
def remove_logo(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SiteBrandOut:
    _require_site_admin(user)
    row = clear_logo(db)
    return SiteBrandOut(
        site_name=row.site_name,
        site_tagline=row.site_tagline,
        has_logo=False,
        logo_version=row.logo_version or 0,
        is_site_admin=True,
    )


def _llm_out(db: Session) -> LLMSettingsOut:
    """把生效配置摊开给前端，但只给 Key 的尾号。"""
    row = get_settings(db)
    cfg = llm.resolve(db)
    from_db = bool((row.llm_api_key or "").strip())
    return LLMSettingsOut(
        base_url=cfg.base_url,
        model=cfg.chat_model,
        api_key_hint=mask_key(cfg.api_key),
        has_api_key=bool(cfg.api_key),
        api_key_source="settings" if from_db else ("env" if cfg.api_key else "none"),
        embedding_model=settings.embedding_model,
        embedding_dim=settings.embedding_dim,
    )


@router.get("/site/llm", response_model=LLMSettingsOut)
def read_llm(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> LLMSettingsOut:
    _require_site_admin(user, "查看")
    return _llm_out(db)


@router.patch("/site/llm", response_model=LLMSettingsOut)
def patch_llm(
    body: LLMSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LLMSettingsOut:
    _require_site_admin(user)
    row = get_settings(db)
    if body.base_url is not None:
        row.llm_base_url = body.base_url.strip() or None
    if body.model is not None:
        row.llm_model = body.model.strip() or None
    if body.clear_api_key:
        # 清掉设置页的值，回退到 .env。
        row.llm_api_key = None
    elif body.api_key is not None:
        # 传空串等于没改，避免「清空输入框再保存」把 Key 误删。
        if body.api_key.strip():
            row.llm_api_key = body.api_key.strip()
    db.commit()
    db.refresh(row)
    return _llm_out(db)


@router.post("/site/llm/test")
def test_llm(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, str]:
    """真发一条最小请求，确认 base_url / Key / 模型名三者能配合。"""
    _require_site_admin(user)
    cfg = llm.resolve(db)
    if not cfg.api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="还没有配置 API Key")
    try:
        reply = llm.chat_completion(
            [{"role": "user", "content": "只回复 ok 两个字母，不要其他内容。"}], db=db
        )
    except Exception as exc:  # noqa: BLE001 - 供应商错误类型不统一，统一转成提示
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"调用失败：{exc}"
        ) from exc
    return {"model": cfg.chat_model, "reply": reply[:200]}
