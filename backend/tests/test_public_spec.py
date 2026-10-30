import json

from app.services.openapi import done_endpoints, filter_public_spec


def _spec() -> str:
    return json.dumps(
        {
            "openapi": "3.0.3",
            "info": {"title": "Demo", "version": "1.0.0"},
            "servers": [{"url": "https://api.example.com"}],
            "x-categories": ["用户", "草稿"],
            "paths": {
                "/users": {
                    "get": {"summary": "列表", "x-status": "done", "tags": ["用户"], "responses": {}},
                    "post": {"summary": "创建", "x-status": "undone", "tags": ["用户"], "responses": {}},
                },
                "/drafts": {
                    "put": {"summary": "草稿", "x-status": "undone", "tags": ["草稿"], "responses": {}},
                },
                "/health": {"get": {"summary": "健康", "responses": {}}},
            },
        }
    )


def test_keeps_only_done_operations():
    data = json.loads(filter_public_spec(_spec()))
    assert set(data["paths"]) == {"/users"}
    assert set(data["paths"]["/users"]) == {"get"}


def test_drops_untagged_and_unused_categories():
    data = json.loads(filter_public_spec(_spec()))
    assert data["x-categories"] == ["用户"]
    assert data["info"]["title"] == "Demo"


def test_returns_input_when_not_json():
    assert filter_public_spec("not json") == "not json"


def test_strips_internal_notes():
    spec = json.loads(_spec())
    spec["x-notes"] = "内部说明"
    spec["paths"]["/users"]["get"]["x-notes"] = "负责人 @a"
    text = filter_public_spec(json.dumps(spec))
    assert "内部说明" not in text
    assert "负责人" not in text


def test_endpoint_keys_narrow_the_view():
    keys = ["GET /users"]
    data = json.loads(filter_public_spec(_spec(), keys))
    assert set(data["paths"]) == {"/users"}
    assert set(data["paths"]["/users"]) == {"get"}
    # 只保留白名单里实际存在的接口，未完成的仍被状态过滤挡住
    none = json.loads(filter_public_spec(_spec(), ["POST /users"]))
    assert none["paths"] == {}


def test_done_endpoints_lists_only_finished():
    spec = json.loads(_spec())
    spec["paths"]["/x"] = {"post": {"x-status": "done"}}
    spec["paths"]["/y"] = {"get": {"x-status": "undone"}}
    assert done_endpoints(json.dumps(spec)) == ["GET /users", "POST /x"]
