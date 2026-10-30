import ipaddress
import socket
import time
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Document, User
from app.services.access import require_role

router = APIRouter(tags=["api-proxy"])

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
MAX_BODY = 1_000_000


class ProxyIn(BaseModel):
    document_id: UUID
    method: str = Field(pattern="^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$")
    url: str = Field(min_length=8, max_length=2000)
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None


class ProxyOut(BaseModel):
    status_code: int
    elapsed_ms: int
    headers: dict[str, str]
    body: str
    error: str | None = None


def _public_ip(host: str) -> None:
    if host.lower() in BLOCKED_HOSTS or host.endswith(".local"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不允许访问内网地址")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法解析主机名") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不允许访问内网地址")


def _allowed_url(spec: dict, url: str) -> bool:
    parsed = urlparse(url)
    servers: list[str] = []
    for item in spec.get("servers") or []:
        if isinstance(item, dict) and item.get("url"):
            servers.append(str(item["url"]).rstrip("/"))
    host = spec.get("host")
    if host:
        scheme = (spec.get("schemes") or ["https"])[0]
        servers.append(f"{scheme}://{host}{spec.get('basePath') or ''}".rstrip("/"))
    if not servers:
        return True
    target = url.rstrip("/")
    netloc = parsed.netloc.lower()
    for server in servers:
        if target.startswith(server) or urlparse(server).netloc.lower() == netloc:
            return True
    return False


@router.post("/spaces/{space_id}/api-proxy", response_model=ProxyOut)
def api_proxy(
    space_id: UUID,
    body: ProxyIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProxyOut:
    require_role(db, user, space_id, "viewer")
    document = db.get(Document, body.document_id)
    if document is None or document.space_id != space_id or document.source_type != "openapi":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API 文档不存在")
    try:
        import json

        spec = json.loads(document.content_md or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OpenAPI 无法解析") from exc

    parsed = urlparse(body.url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入有效的 http(s) 地址")
    _public_ip(parsed.hostname)
    if not _allowed_url(spec, body.url.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能调试该文档 servers 中的地址")

    hop = {"host", "content-length", "connection", "transfer-encoding"}
    headers = {k: v for k, v in body.headers.items() if k.lower() not in hop and not k.lower().startswith("x-forwarded")}
    started = time.perf_counter()
    try:
        with httpx.Client(follow_redirects=False, timeout=20.0, verify=True) as client:
            response = client.request(
                body.method,
                body.url.strip(),
                headers=headers,
                content=body.body.encode("utf-8") if body.body and body.method not in {"GET", "HEAD"} else None,
            )
    except httpx.HTTPError as exc:
        return ProxyOut(
            status_code=0,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            headers={},
            body="",
            error=str(exc),
        )
    text = response.text
    if len(text) > MAX_BODY:
        text = text[:MAX_BODY] + "\n…(已截断)"
    return ProxyOut(
        status_code=response.status_code,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        headers={k: v for k, v in list(response.headers.items())[:40]},
        body=text,
        error=None,
    )
