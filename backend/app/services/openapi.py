import json

from fastapi import HTTPException, status

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

# 外部访问默认只暴露已完成接口；endpoint_keys 非空时再按白名单收窄。
ALLOWED_STATUSES = ("done",)


def _param_text(param: object) -> str:
    """把一个参数压成一行，接口名、位置、类型、说明都要能被检索到。"""
    if not isinstance(param, dict):
        return ""
    name = str(param.get("name") or "").strip()
    if not name:
        return ""
    schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
    parts = [name]
    location = str(param.get("in") or "").strip()
    if location:
        parts.append(f"({location}")
        kind = str(schema.get("type") or "").strip()
        parts.append(f", {kind})" if kind else ")")
    description = str(param.get("description") or "").strip()
    if description:
        parts.append(f" {description}")
    return "".join(parts)


def _spec_body_text(data: dict) -> str:
    """把 OpenAPI 展开成可检索的纯文本。

    只索引 title + path 会让接口名、说明、参数全部搜不到，
    所以这里把每个接口的方法、摘要、说明、分组、参数、响应都摊平进去。
    """
    lines: list[str] = []
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    title = str(info.get("title") or "").strip()
    if title:
        lines.append(title)
    description = str(info.get("description") or "").strip()
    if description:
        lines.append(description)

    paths = data.get("paths")
    if not isinstance(paths, dict):
        return "\n".join(lines)

    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method not in METHODS or not isinstance(op, dict):
                continue
            head = f"{method.upper()} {path}"
            summary = str(op.get("summary") or "").strip()
            if summary:
                head = f"{head} {summary}"
            lines.append(head)
            tags = [str(tag).strip() for tag in (op.get("tags") or []) if str(tag).strip()]
            if tags:
                lines.append("分组 " + " ".join(tags))
            op_description = str(op.get("description") or "").strip()
            if op_description:
                lines.append(op_description)
            parameters = op.get("parameters") if isinstance(op.get("parameters"), list) else []
            for param in parameters:
                text = _param_text(param)
                if text:
                    lines.append(f"参数 {text}")
            body = op.get("requestBody")
            if isinstance(body, dict):
                body_description = str(body.get("description") or "").strip()
                if body_description:
                    lines.append(f"请求体 {body_description}")
            responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
            for code, response in responses.items():
                if not isinstance(response, dict):
                    continue
                response_description = str(response.get("description") or "").strip()
                if response_description:
                    lines.append(f"响应 {code} {response_description}")
    return "\n".join(lines)


def endpoint_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def normalize_endpoint_key(key: str) -> str:
    """只把方法部分转大写，路径大小写必须原样保留。"""
    method, _, path = (key or "").strip().partition(" ")
    return endpoint_key(method, path.strip())


def _public_server(servers: list) -> dict:
    """对外只暴露公网入口：跳过 localhost / 内网地址，找不到就退回第一个。"""
    def host_of(item: object) -> str:
        url = item.get("url") if isinstance(item, dict) else item
        return str(url or "")

    def is_private(url: str) -> bool:
        lowered = url.lower()
        return any(
            token in lowered
            for token in ("localhost", "127.0.0.1", "0.0.0.0", "://10.", "://192.168.", "://172.16.")
        )

    public = [item for item in servers if not is_private(host_of(item))]
    return (public or servers)[0]


def done_endpoints(spec_text: str) -> list[str]:
    """列出可用于白名单选择的已完成接口，供分享设置界面展示。"""
    try:
        data = json.loads(spec_text or "")
    except (ValueError, TypeError):
        return []
    if not isinstance(data, dict) or not isinstance(data.get("paths"), dict):
        return []
    keys: list[str] = []
    for path, item in data["paths"].items():
        if not isinstance(item, dict):
            continue
        for name, op in item.items():
            if name in METHODS and isinstance(op, dict) and op.get("x-status") == "done":
                keys.append(endpoint_key(name, path))
    return keys


def filter_public_spec(spec_text: str, endpoint_keys: list[str] | None = None) -> str:
    """外部访问只暴露标记为已完成的接口；给了白名单则只保留其中列出的接口。"""
    try:
        data = json.loads(spec_text or "")
    except (ValueError, TypeError):
        return spec_text
    if not isinstance(data, dict) or not isinstance(data.get("paths"), dict):
        return spec_text

    allow = {normalize_endpoint_key(key) for key in endpoint_keys} if endpoint_keys else None

    kept: dict[str, dict] = {}
    for path, item in data["paths"].items():
        if not isinstance(item, dict):
            continue
        operations = {
            name: op
            for name, op in item.items()
            if name in METHODS
            and isinstance(op, dict)
            and op.get("x-status") in ALLOWED_STATUSES
            and (allow is None or endpoint_key(name, path) in allow)
        }
        if operations:
            kept[path] = {**{k: v for k, v in item.items() if k not in METHODS}, **operations}

    result = {key: value for key, value in data.items() if key != "paths"}
    # 内部备注（x-notes）只给团队看，公开链接里直接剔除，避免前端隐藏后又从 JSON 漏出。
    result.pop("x-notes", None)
    info = result.get("info")
    if isinstance(info, dict):
        info.pop("x-notes", None)
    # 环境列表常含内网 / 测试地址，对外只保留一个可公开访问的入口。
    result.pop("x-environments", None)
    servers = result.get("servers")
    if isinstance(servers, list) and servers:
        result["servers"] = [_public_server(servers)]
    result["paths"] = kept

    used_tags: set[str] = set()
    for item in kept.values():
        for name, op in item.items():
            if name in METHODS:
                op.pop("x-notes", None)
                used_tags.update(op.get("tags") or [])
    for key in ("x-categories",):
        categories = result.get(key)
        if isinstance(categories, list):
            result[key] = [tag for tag in categories if tag in used_tags]
    return json.dumps(result, ensure_ascii=False, indent=2)


def parse_openapi(spec_text: str) -> tuple[dict, str, str, str]:
    raw = (spec_text or "").strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请粘贴 OpenAPI JSON 或 YAML")
    data = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        if yaml is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不是有效的 JSON，且当前未启用 YAML 解析")
        try:
            data = yaml.safe_load(raw)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法解析 OpenAPI 文档") from exc
    if not isinstance(data, dict) or not (data.get("openapi") or data.get("swagger") or data.get("paths")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不是有效的 OpenAPI / Swagger 文档")
    title = str((data.get("info") or {}).get("title") or "API 文档")[:500]
    stored = json.dumps(data, ensure_ascii=False, indent=2)
    content_text = _spec_body_text(data)
    if not content_text.strip():
        content_text = title
    return data, title, stored, content_text
