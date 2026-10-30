"""跨空间检索的边界。

要点：可见空间只能来自数据库里的成员关系，不能由前端指定；
以及「全部空间」的历史只取 space_id 为空的记录。
"""

import uuid

from app.services.search import hybrid_search_multi


class FakeDB:
    """只记录 SQL 参数，用来断言传下去的 space_ids。"""

    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        raise AssertionError("不应真的查库")

    def get(self, _model, _pk):
        """模型配置读不到，走 .env 兜底。"""
        return None


def test_empty_space_list_short_circuits():
    """一个可见空间都没有时直接返回，不发起无意义的 IN () 查询。"""
    db = FakeDB()
    assert hybrid_search_multi(db, [], "任意关键词") == []
    assert db.calls == []


def test_single_space_still_matches_multi_space_path(monkeypatch):
    """单空间检索应该复用多空间那条路径，避免两套 SQL 逻辑漂移。"""
    captured = {}

    def fake(db, space_ids, query, limit):
        captured["ids"] = space_ids
        return []

    monkeypatch.setattr("app.services.search._fts_and_like", fake)
    # 关掉向量检索，只验证关键词那条路径的 space_ids 传递。
    monkeypatch.setattr("app.services.search.llm.configured", lambda _db=None: False)
    sid = uuid.uuid4()
    hybrid_search_multi(db=FakeDB(), space_ids=[sid], query="权限")
    assert captured["ids"] == [sid]


def test_global_log_filter_uses_null_space():
    """「全部空间」的历史必须只取 space_id 为空的记录。"""
    from app.services.history import list_search_logs

    class Result:
        def all(self):
            return []

    class Recorder:
        def __init__(self):
            self.statements = []

        def scalar(self, statement):
            self.statements.append(str(statement))
            return 0

        def scalars(self, statement):
            self.statements.append(str(statement))
            return Result()

    db = Recorder()
    items, total = list_search_logs(
        db, space_id=None, user_id=uuid.uuid4(), page=1, page_size=20
    )
    assert items == [] and total == 0
    joined = " ".join(db.statements)
    assert "space_id IS NULL" in joined
    # 不能连别人在「全部空间」里搜的记录也一起读出来。
    assert "user_id" in joined
