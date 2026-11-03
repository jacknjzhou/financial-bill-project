"""T6 对账项目：ReconcileProject 校验（类型-数据源组合/筛选条件/起始日期）。"""
import pytest
from django.test import Client

from apps.accounts.models import User

VALID_PROJECT = {
    "name": "微信交易对账",
    "type": "transaction",
    "a_source": "payment",
    "a_filter": [],
    "b_source": "clearing",
    "b_filter": [],
    "match_key": "order_no",
    "a_status_set": ["SUCCESS"],
    "b_status_set": ["SUCCESS"],
    "b_sum": False,
    "start_date": "2026-10-01",
    "exec_time": "02:00",
}


@pytest.fixture
def client(db):
    admin = User.objects.create_user(
        "admin", password="Admin@123", role=User.Role.ADMIN, must_change_password=False
    )
    c = Client()
    c.force_login(admin)
    return c


def _create(client, **overrides):
    return client.post(
        "/api/v1/reconcile-projects", data={**VALID_PROJECT, **overrides}, content_type="application/json"
    )


class ProjectTest:
    def test_create_transaction_project(self, client):
        r = _create(client)
        assert r.status_code == 201, r.content
        assert r.json()["last_date"] is None

    def test_transaction_requires_payment_vs_clearing(self, client):
        r = _create(client, a_source="clearing")
        assert r.status_code == 400
        r = _create(client, b_source="payment")
        assert r.status_code == 400

    def test_type_source_combos(self, client):
        # fund 允许 clearing/settlement 组合
        r = _create(client, type="fund", a_source="clearing", b_source="settlement")
        assert r.status_code == 201, r.content
        # transaction 传 settlement → 400
        r = _create(client, b_source="settlement")
        assert r.status_code == 400

    def test_filter_json(self, client):
        r = _create(client, a_filter={"field": "channel"})  # 非列表 → 400
        assert r.status_code == 400
        r = _create(client, a_filter=[{"field": "bad_field", "op": "eq", "value": 1}])
        assert r.status_code == 400

    def test_update_start_date_not_past(self, client):
        r = _create(client)
        pid = r.json()["id"]
        # 一期先校验：不得早于最后对账日期（run 在 T9 产生后走该分支）
        r = client.patch(
            f"/api/v1/reconcile-projects/{pid}",
            data={"last_date": "2026-10-20", "start_date": "2026-10-01"},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_schema(self, client):
        from tests.conftest import list_items_component, resolve_node

        s = client.get("/api/schema", HTTP_ACCEPT="application/json").json()
        item = list_items_component(s, "/api/v1/reconcile-projects")
        t = resolve_node(s, item["properties"]["type"])
        assert t["enum"] == ["transaction", "fund", "balance"]
        assert item["properties"]["a_status_set"]["type"] == "array"
