"""T2 认证与角色：登录 / me / 强制改密 / 角色权限 / 未设密码设密。

会话认证（Django session）；must_change_password 期间会话被中间件
限制到 /api/v1/auth/* 白名单端点（业务 API 一律 403 MUST_CHANGE_PASSWORD）。
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

User = get_user_model()

BACKEND = "django.contrib.auth.backends.ModelBackend"

factory = APIRequestFactory()


@pytest.fixture
def users(db):
    admin = User.objects.create_user("admin", password="Admin@123", role=User.Role.ADMIN)
    admin.must_change_password = True
    admin.save()
    op = User.objects.create_user(
        "zhangsan", password="Op@12345", role=User.Role.OPERATOR, must_change_password=False
    )
    return admin, op


def _login(username: str, password: str) -> Client:
    c = Client()
    c.post("/api/v1/auth/login", data={"username": username, "password": password})
    return c


class LoginTest:
    def test_login_success(self, db, users):
        c = _login("admin", "Admin@123")
        r = c.post("/api/v1/auth/login", data={"username": "admin", "password": "Admin@123"})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["username"] == "admin"
        assert body["user"]["role"] == "admin"
        assert body["user"]["must_change_password"] is True
        assert body["must_change_password"] is True

    def test_login_wrong_password(self, db, users):
        r = Client().post("/api/v1/auth/login", data={"username": "admin", "password": "wrong"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_disabled_user_rejected(self, db, users):
        admin, _ = users
        admin.is_active = False
        admin.save()
        r = Client().post("/api/v1/auth/login", data={"username": "admin", "password": "Admin@123"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"  # 不泄漏停用细节

    def test_csrf_cookie_endpoint(self, db):
        # 前端登录后首个 POST 需要 csrftoken cookie（axios 自动带 X-XSRFToken）
        c = Client()
        assert c.get("/api/v1/auth/csrf").status_code == 200
        assert "csrftoken" in c.cookies


class MeTest:
    def test_me_requires_login(self, db):
        assert Client().get("/api/v1/auth/me").status_code == 401

    def test_me_returns_user(self, db, users):
        c = _login("zhangsan", "Op@12345")
        r = c.get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.json()["username"] == "zhangsan"
        assert r.json()["role"] == "operator"
        assert r.json()["must_change_password"] is False

    def test_logout(self, db, users):
        c = _login("zhangsan", "Op@12345")
        assert c.post("/api/v1/auth/logout").status_code == 200
        assert c.get("/api/v1/auth/me").status_code == 401


class MustChangePasswordGateTest:
    """首登强制改密：会话限定在 /api/v1/auth/* 白名单。"""

    def _admin(self, users):
        admin, _ = users
        c = Client()
        c.force_login(admin, backend=BACKEND)  # 模拟已登录会话（must_change_password=True）
        return c

    def test_business_api_blocked(self, db, users):
        c = self._admin(users)
        # 用一个受保护的探针端点代表“业务 API”（走全局中间件）
        r = c.get("/api/v1/auth/me")  # me 在白名单内 → 200 且带标志
        assert r.status_code == 200
        assert r.json()["must_change_password"] is True
        # 非白名单业务路径 → 403 MUST_CHANGE_PASSWORD
        r = c.get("/api/v1/channels")
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "MUST_CHANGE_PASSWORD"

    def test_change_password_unlocks(self, db, users):
        c = self._admin(users)
        r = c.post(
            "/api/v1/auth/change-password",
            data={"old_password": "Admin@123", "new_password": "NewPass@1"},
        )
        assert r.status_code == 200
        r = c.get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.json()["must_change_password"] is False
        # 业务 API 放行
        assert c.get("/api/v1/channels").status_code in (200, 404)

    def test_change_password_wrong_old(self, db, users):
        c = self._admin(users)
        r = c.post(
            "/api/v1/auth/change-password",
            data={"old_password": "bad", "new_password": "NewPass@1"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_set_password_without_old(self, db):
        # SSO 自动建号的用户：本地密码未设 → 免旧密码直接设置
        u = User.objects.create_user("ssouser")
        u.set_unusable_password()
        u.role = User.Role.OPERATOR
        u.must_change_password = False
        u.save()
        c = Client()
        c.force_login(u, backend=BACKEND)
        r = c.post("/api/v1/auth/change-password", data={"new_password": "NewPass@1"})
        assert r.status_code == 200
        # 设后可用新密码本地登录（两种登录模式并存）
        c2 = Client()
        assert (
            c2.post(
                "/api/v1/auth/login",
                data={"username": "ssouser", "password": "NewPass@1"},
            ).status_code
            == 200
        )

    def test_change_password_requires_old_when_set(self, db, users):
        # 已设密码的用户免旧密码 → 400
        c = _login("zhangsan", "Op@12345")
        r = c.post("/api/v1/auth/change-password", data={"new_password": "NewPass@1"})
        assert r.status_code == 400


class RolePermissionTest:
    """RoleRequired 权限类（端点级 403 用例在 T4/T14 落地后覆盖）。"""

    def test_probe_admin_only(self, db, users):
        from apps.core.permissions import IsAdmin

        class _Probe(APIView):
            permission_classes = [IsAdmin]

            def get(self, request):
                return Response({"ok": True})

        admin, op = users
        for user, expected in ((admin, 200), (op, 403)):
            request = factory.get("/probe")
            force_authenticate(request, user=user)
            resp = _Probe.as_view()(request)
            assert resp.status_code == expected

    def test_probe_operator(self, db, users):
        from apps.core.permissions import IsAdminOrOperator

        class _Probe(APIView):
            permission_classes = [IsAdminOrOperator]

            def get(self, request):
                return Response({"ok": True})

        admin, op = users
        for user, expected in ((admin, 200), (op, 200)):  # 两角色都放行
            request = factory.get("/probe")
            force_authenticate(request, user=user)
            resp = _Probe.as_view()(request)
            assert resp.status_code == expected
