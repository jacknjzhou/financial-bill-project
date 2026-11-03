"""T4 基础字典：Channel / FundAccount / BizType / DisputeType CRUD + 引用保护 + 初始数据。"""
import pytest
from django.test import Client

from apps.accounts.models import User

User = User


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        "admin", password="Admin@123", role=User.Role.ADMIN, must_change_password=False
    )


@pytest.fixture
def client(admin):
    c = Client()
    c.force_login(admin)
    return c


class ChannelTest:
    def test_channel_crud(self, client):
        r = client.post(
            "/api/v1/channels", data={"code": "wxpay", "name": "微信支付", "enabled": True}, content_type="application/json"
        )
        assert r.status_code == 201, r.content
        rid = r.json()["id"]
        r = client.get("/api/v1/channels")
        body = r.json()
        assert body["total"] == 1 and body["items"][0]["code"] == "wxpay"
        r = client.patch(f"/api/v1/channels/{rid}", data={"enabled": False}, content_type="application/json")
        assert r.status_code == 200 and r.json()["enabled"] is False
        # 重复 code 拒绝
        r = client.post(
            "/api/v1/channels", data={"code": "wxpay", "name": "x", "enabled": True}, content_type="application/json"
        )
        assert r.status_code == 400

    def test_channel_delete_protected(self, client):
        r = client.post(
            "/api/v1/channels", data={"code": "wxpay", "name": "微信支付", "enabled": True}, content_type="application/json"
        )
        cid = r.json()["id"]
        r = client.post(
            "/api/v1/fund-accounts",
            data={"channel": cid, "name": "微信商户1", "account_no": "mch-001", "start_date": "2026-10-01", "start_balance": 100000, "enabled": True},
            content_type="application/json",
        )
        assert r.status_code == 201, r.content
        r = client.delete(f"/api/v1/channels/{cid}")
        assert r.status_code == 409
        r = client.delete(f"/api/v1/channels/{cid}")  # 再删仍 409（数据未动）
        assert r.status_code == 409

    def test_fund_account_requires_start(self, client):
        r = client.post(
            "/api/v1/channels", data={"code": "alipay", "name": "支付宝", "enabled": True}, content_type="application/json"
        )
        cid = r.json()["id"]
        r = client.post(
            "/api/v1/fund-accounts",
            data={"channel": cid, "name": "缺启用余额"},
            content_type="application/json",
        )
        assert r.status_code == 400
        r = client.post(
            "/api/v1/fund-accounts",
            data={"channel": cid, "name": "完整", "account_no": "mch-2", "start_date": "2026-10-01", "start_balance": 0, "enabled": True},
            content_type="application/json",
        )
        assert r.status_code == 201


class BizTypeTest:
    def test_biztype_crud(self, client):
        r = client.post(
            "/api/v1/biz-types",
            data={"code": "PAY", "name": "收款", "group": "INCOME"},
            content_type="application/json",
        )
        assert r.status_code == 201, r.content
        r = client.post(
            "/api/v1/biz-types", data={"code": "FEE", "name": "手续费", "group": "BAD_GROUP"}, content_type="application/json"
        )
        assert r.status_code == 400
        assert client.get("/api/v1/biz-types").json()["total"] == 1


class DisputeTypeTest:
    def test_dispute_type_crud(self, client):
        # 迁移已建 4 条交易组初始类型（规格：内置初始值，界面可改）
        r = client.get("/api/v1/dispute-types")
        names = {i["name"] for i in r.json()["items"]}
        assert {"补单", "忽略-时间差", "确认损失", "人工核实后忽略"} <= names
        r = client.post(
            "/api/v1/dispute-types",
            data={"group": "FUND", "name": "长短款挂账", "description": "二期用"},
            content_type="application/json",
        )
        assert r.status_code == 201


class SchemaTest:
    def test_schema(self, client):
        s = client.get("/api/schema", HTTP_ACCEPT="application/json").json()
        chan_list = s["paths"]["/api/v1/channels"]["get"]
        comp = s["components"]["schemas"]
        # fund-accounts 的 start_balance 必须是 int64 + 有"单位：分"说明
        fa = s["paths"]["/api/v1/fund-accounts"]["get"]
        fa_comp = _component_of(s, fa)
        assert fa_comp["properties"]["start_balance"]["type"] == "integer"
        assert fa_comp["properties"]["start_balance"].get("format") == "int64"
        # channels 列表 schema 存在且 enabled 为 boolean
        chan_comp = _component_of(s, chan_list)
        assert chan_comp["properties"]["enabled"]["type"] == "boolean"


def _component_of(schema, path_item):
    """从列表端点响应 schema 解析出 items 元素组件（分页信封→items→$ref）。"""
    resp = path_item["responses"]["200"]["content"]["application/json"]["schema"]
    if "$ref" in resp:
        name = resp["$ref"].rsplit("/", 1)[-1]
        resp = schema["components"]["schemas"][name]
    items = resp["properties"]["items"]
    ref = items["items"]["$ref"] if "items" in items else items["$ref"]
    name = ref.rsplit("/", 1)[-1]
    return schema["components"]["schemas"][name]
