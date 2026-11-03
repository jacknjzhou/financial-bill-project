"""T5 解析规则与获取任务：ParseRule / FetchTask CRUD + 校验 + schema。"""
import pytest
from django.test import Client

from apps.accounts.models import User

VALID_RULE = {
    "name": "微信清算模板",
    "target": "clearing",
    "file_format": "csv",
    "delimiter": ",",
    "header_row": 1,
    "column_map": {"商户单号": "order_no", "金额": "amount", "状态": "status", "": ""},
    "value_maps": {"status": {"成功": "SUCCESS"}},
    "amount_scale": 100,
    "time_format": "%Y-%m-%d %H:%M:%S",
}


@pytest.fixture
def client(db):
    admin = User.objects.create_user(
        "admin", password="Admin@123", role=User.Role.ADMIN, must_change_password=False
    )
    c = Client()
    c.force_login(admin)
    return c


class ParseRuleTest:
    def test_parse_rule_valid(self, client):
        r = client.post("/api/v1/parse-rules", data=VALID_RULE, content_type="application/json")
        assert r.status_code == 201, r.content
        assert r.json()["column_map"]["商户单号"] == "order_no"

    def test_parse_rule_invalid_target(self, client):
        bad = {**VALID_RULE, "target": "foo"}
        r = client.post("/api/v1/parse-rules", data=bad, content_type="application/json")
        assert r.status_code == 400

    def test_parse_rule_empty_mapping(self, client):
        bad = {**VALID_RULE, "column_map": {}}
        r = client.post("/api/v1/parse-rules", data=bad, content_type="application/json")
        assert r.status_code == 400
        details = r.json()["error"]["details"]
        text = str(details)
        assert "至少映射一个字段" in text, details

    def test_default_templates_seeded(self, client):
        """规格：内置默认解析模板（自有支付/微信清算/支付宝结算），界面可改。"""
        r = client.get("/api/v1/parse-rules")
        names = {i["name"] for i in r.json()["items"]}
        assert {"自有支付导出", "微信支付清算文件", "支付宝结算文件"} <= names

    def test_schema(self, client):
        from tests.conftest import list_items_component, resolve_node

        s = client.get("/api/schema", HTTP_ACCEPT="application/json").json()
        item = list_items_component(s, "/api/v1/parse-rules")
        target = resolve_node(s, item["properties"]["target"])
        assert target["enum"] == ["payment", "clearing", "settlement"]


class FetchTaskTest:
    def test_fetch_task(self, client):
        rule = client.post("/api/v1/parse-rules", data=VALID_RULE, content_type="application/json").json()
        ch = client.post(
            "/api/v1/channels", data={"code": "wxpay", "name": "微信", "enabled": True}, content_type="application/json"
        ).json()
        r = client.post(
            "/api/v1/fetch-tasks",
            data={"name": "微信清算每日上传", "side": "channel", "channel": ch["id"], "parse_rule": rule["id"]},
            content_type="application/json",
        )
        assert r.status_code == 201, r.content
        assert r.json()["mode"] == "manual_upload"
        r = client.get("/api/v1/fetch-tasks")
        assert r.json()["total"] == 1
