"""全站品牌设置。

重点在两条容易出错的规则：
1. 只有站内第一个账号能拿到站点管理员，后续注册的人不能自动提权。
2. Logo 的类型和体积限制必须真的挡住，否则什么都往里传。
"""

import uuid

from app.services.site import DEFAULT_NAME, MAX_LOGO_BYTES, get_settings


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def where(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def __iter__(self):
        return iter(self._result)


class FakeSession:
    """只够跑 should_become_site_admin / ensure_site_admin 的最小实现。"""

    def __init__(self, admins, users):
        self.admins = admins
        self.users = users
        self.committed = False

    def scalar(self, _statement):
        return self.admins[0] if self.admins else None

    def commit(self):
        self.committed = True


def test_has_admin_blocks_promotion(monkeypatch):
    """已经有超管时，新注册的人不该被提权。"""
    from app.services import site

    monkeypatch.setattr(site, "select", lambda *a, **k: FakeQuery([]))
    fake = FakeSession(admins=[uuid.uuid4()], users=[])
    assert site.should_become_site_admin(fake) is False


def test_no_admin_triggers_promotion():
    from app.services import site

    fake = FakeSession(admins=[], users=[])
    assert site.should_become_site_admin(fake) is True


def test_ensure_promotes_earliest_user(monkeypatch):
    """老库里一个超管都没有时，把最早注册的账号补成超管。"""
    from app.services import site

    class User:
        is_site_admin = False

    first = User()
    state = {"admins": []}

    class Sess(FakeSession):
        def scalar(self, _statement):
            # 第一次问「有没有超管」，第二次取最早的用户。
            if not state.get("asked"):
                state["asked"] = True
                return None
            return first

    fake = Sess(admins=[], users=[first])
    site.ensure_site_admin(fake)
    assert first.is_site_admin is True
    assert fake.committed is True


def test_logo_size_limit_is_sane():
    """限制得比常规图片大、比整页截图小，512KB 是合理的上传上限。"""
    assert MAX_LOGO_BYTES == 512 * 1024


def test_default_name_is_non_empty():
    """默认站名不能是空串，否则左上角会空一块。"""
    assert DEFAULT_NAME.strip()


def test_mask_key_hides_middle():
    """脱敏只能露出头尾，中间必须遮掉，否则等于没脱敏。"""
    from app.services.site import mask_key

    masked = mask_key("sk-abcdefghijklmnopqrstuvwxyz")
    assert masked.startswith("sk-")
    assert masked.endswith("wxyz")
    assert "abcdefghij" not in masked


def test_mask_key_handles_empty():
    from app.services.site import mask_key

    assert mask_key("") == ""
    assert mask_key(None) == ""


def test_resolve_prefers_db_over_env(monkeypatch):
    """设置页填了就优先用数据库的值，留空才回退到 .env。"""
    from app.services import llm

    class Row:
        llm_base_url = "https://custom.example/v1"
        llm_model = "custom-model"
        llm_api_key = "sk-custom"

    class DB:
        def get(self, _model, _pk):
            return Row()

    class EmptyRow:
        llm_base_url = None
        llm_model = None
        llm_api_key = None

    class EmptyDB:
        def get(self, _model, _pk):
            return EmptyRow()

    cfg = llm.resolve(DB())
    assert cfg.base_url == "https://custom.example/v1"
    assert cfg.chat_model == "custom-model"

    fallback = llm.resolve(EmptyDB())
    from app.config import settings

    assert fallback.base_url == settings.openai_base_url
    assert fallback.chat_model == settings.openai_model
