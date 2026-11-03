"""T14 用户管理：admin 限定 CRUD + 自我保护 + 密码重置。"""
import pytest
from django.test import Client

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(db):
    return User.objects.create_user("admin", password="Admin@123", role=User.Role.ADMIN, must_change_password=False)


@pytest.fixture
def operator(db):
    return User.objects.create_user("op1", password="Op@12345", role=User.Role.OPERATOR, must_change_password=False)


@pytest.fixture
def admin_client(admin):
    c = Client()
    c.force_login(admin)
    return c


class TestUsers:
    def test_admin_crud(self, admin_client):
        r = admin_client.post("/api/v1/users", data={"username": "op2", "password": "Op@12345", "role": "operator"}, content_type="application/json")
        assert r.status_code == 201, r.content
        uid = r.json()["id"]
        r = admin_client.patch(f"/api/v1/users/{uid}", data={"role": "admin"}, content_type="application/json")
        assert r.status_code == 200 and r.json()["role"] == "admin"
        r = admin_client.patch(f"/api/v1/users/{uid}", data={"is_active": False}, content_type="application/json")
        assert r.json()["is_active"] is False
        r = admin_client.get("/api/v1/users", {"role": "operator"})
        assert r.json()["total"] == 0  # op2 已改为 admin

    def test_operator_forbidden(self, operator):
        c = Client()
        c.force_login(operator)
        assert c.get("/api/v1/users").status_code == 403
        r = c.post("/api/v1/users", data={"username": "x", "password": "X@123456", "role": "operator"}, content_type="application/json")
        assert r.status_code == 403

    def test_self_protect(self, admin, admin_client):
        r = admin_client.patch(f"/api/v1/users/{admin.id}", data={"is_active": False}, content_type="application/json")
        assert r.status_code == 409
        r = admin_client.delete(f"/api/v1/users/{admin.id}")
        assert r.status_code == 409

    def test_dup_username(self, admin_client, operator):
        r = admin_client.post("/api/v1/users", data={"username": "op1", "password": "Op@12345", "role": "operator"}, content_type="application/json")
        assert r.status_code == 400

    def test_reset_password(self, admin_client, operator):
        r = admin_client.post(f"/api/v1/users/{operator.id}/reset-password", data={"new_password": "New@12345"}, content_type="application/json")
        assert r.status_code == 200
        c = Client()
        assert c.login(username="op1", password="New@12345")

    def test_schema(self, admin_client):
        from tests.conftest import resolve_node

        s = admin_client.get("/api/schema", HTTP_ACCEPT="application/json").json()
        resp = s["paths"]["/api/v1/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        comp = resolve_node(s, resp)
        item = resolve_node(s, comp["properties"]["items"]["items"])
        role = resolve_node(s, item["properties"]["role"])
        assert role["enum"] == ["admin", "operator"]
