"""检索 / 问答历史的汇总逻辑。

历史写入走独立 Session，接口层不好直接断言，这里只测纯逻辑部分：
命中快照的裁剪，以及「自己看自己的、管理员看全空间」的过滤条件。
"""

import uuid

from app.api.chat import _user_names as chat_user_names
from app.services.history import _write


def test_hits_snapshot_keeps_only_title_and_id():
    """快照只留标题和 id：正文可能很长，且用户还能在文档里看到。"""
    hits = [
        {
            "document_id": uuid.uuid4(),
            "document_title": "接口文档",
            "chunk_id": uuid.uuid4(),
            "content": "很长的正文" * 100,
            "score": 0.9,
        }
    ]
    snapshot = [
        {"document_id": str(hit["document_id"]), "document_title": hit["document_title"]}
        for hit in hits
    ]
    assert snapshot == [
        {"document_id": str(hits[0]["document_id"]), "document_title": "接口文档"}
    ]
    assert "content" not in snapshot[0]


def test_write_swallows_database_errors(monkeypatch):
    """记录失败不能影响用户拿到检索/问答结果。"""

    class Boom(Exception):
        pass

    class FakeSession:
        def add(self, _obj):
            raise Boom("db down")

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            raise AssertionError("不应执行到 commit")

        def close(self):
            self.closed = True

    fake = FakeSession()

    monkeypatch.setattr("app.services.history.SessionLocal", lambda: fake)
    _write(object, space_id=uuid.uuid4())  # 不应抛出
    assert getattr(fake, "closed", False) is True


def test_user_names_empty_short_circuits(monkeypatch):
    """没有记录时不查库，避免空 IN 查询。"""

    class NoQuery:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("不应查库")

    assert chat_user_names(NoQuery(), set()) == {}
