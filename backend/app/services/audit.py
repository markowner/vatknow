import re
import uuid
from collections.abc import Callable

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.db import SessionLocal
from app.models import AuditLog
from app.services.security import decode_access_token

SPACE_RE = re.compile(r"/spaces/([0-9a-fA-F-]{36})")
SKIP_PREFIXES = ("/health", "/api/v1/health", "/api/v1/public/")
SKIP_SUFFIXES = ("/api-proxy",)


def _action(method: str, path: str) -> str:
    if path.endswith("/auth/login"):
        return "登录"
    if path.endswith("/auth/register"):
        return "注册"
    if path.endswith("/auth/password"):
        return "修改密码"
    if "/members" in path:
        return {"POST": "邀请成员", "PATCH": "变更成员角色", "DELETE": "移除成员"}.get(method, "成员操作")
    if "/shares" in path:
        return {"POST": "创建分享", "DELETE": "撤销分享"}.get(method, "分享操作")
    if path.endswith("/chat"):
        return "知识库问答"
    if "/documents/from-url" in path:
        return "收录网址"
    if "/documents/upload" in path:
        return "上传文档"
    if "/documents/paste" in path:
        return "粘贴网页"
    if "/documents/openapi" in path:
        return "收录 API 文档"
    if "/documents" in path or path.startswith("/api/v1/documents"):
        return {"POST": "创建文档", "PATCH": "更新文档", "DELETE": "删除文档"}.get(method, "文档操作")
    if path.rstrip("/").endswith("/spaces") or "/spaces/" in path:
        return {"POST": "创建空间", "PATCH": "更新空间", "DELETE": "删除空间"}.get(method, "空间操作")
    return f"{method} 操作"


def write_audit(
    *,
    user_id: uuid.UUID | None,
    space_id: uuid.UUID | None,
    action: str,
    method: str,
    path: str,
    status_code: int,
    ip: str | None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AuditLog(
                user_id=user_id,
                space_id=space_id,
                action=action,
                method=method,
                path=path[:400],
                status_code=status_code,
                ip=ip,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        path = request.url.path
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return response
        if any(path.startswith(prefix) or path == prefix.rstrip("/") for prefix in SKIP_PREFIXES):
            return response
        if any(path.endswith(suffix) for suffix in SKIP_SUFFIXES):
            return response
        if not path.startswith("/api/"):
            return response
        user_id = None
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            try:
                user_id = decode_access_token(auth.split(" ", 1)[1])
            except Exception:
                user_id = None
        space_id = None
        match = SPACE_RE.search(path)
        if match:
            try:
                space_id = uuid.UUID(match.group(1))
            except ValueError:
                space_id = None
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else None
        )
        try:
            write_audit(
                user_id=user_id,
                space_id=space_id,
                action=_action(request.method, path),
                method=request.method,
                path=path,
                status_code=response.status_code,
                ip=ip,
            )
        except Exception:
            pass
        return response


def install_audit(app: FastAPI) -> None:
    app.add_middleware(AuditMiddleware)
