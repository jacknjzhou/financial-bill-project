"""T2B SSO / OIDC（allauth openid_connect 客户端）。

全流程用「进程内 mock IdP」验证：真实 HTTP 服务器（127.0.0.1 随机端口）提供
discovery / JWKS / token / userinfo，allauth 客户端走真实 HTTP 往返
（签发并验证 RS256 id_token，无外网依赖）；浏览器 302 链由 test client 手工跟进。
"""
import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from urllib.parse import quote

from allauth.socialaccount.models import SocialApp

User = get_user_model()

PREFIX = "/mock-idp"
CLIENT_ID = "recon-client"
CLIENT_SECRET = "recon-secret"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class MockIdp:
    """进程内 mock IdP：真实 HTTP 服务器，签发 RS256 id_token。"""

    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "recon-kid-1"
        self.claims = {
            "sub": "idp-user-1",
            "preferred_username": "ssouser",
            "email": "ssouser@example.com",
            "email_verified": True,
            "name": "SSO 用户",
            "groups": ["recon-operator"],
        }
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _MockIdpHandler)
        self.server.mock = self
        self.port = self.server.server_address[1]
        self.issuer = f"http://127.0.0.1:{self.port}{PREFIX}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    @property
    def jwks(self) -> dict:
        pub = self.key.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": self.kid,
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64url(pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")),
                    "e": _b64url(pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")),
                }
            ]
        }

    def sign_id_token(self, claims: dict, aud: str) -> str:
        now = int(time.time())
        token_claims = {**claims, "iss": self.issuer, "aud": aud, "iat": now, "exp": now + 3600}
        header = _b64url(json.dumps({"alg": "RS256", "kid": self.kid, "typ": "JWT"}).encode())
        body = _b64url(json.dumps(token_claims).encode())
        sig = self.key.sign(f"{header}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
        return f"{header}.{body}.{_b64url(sig)}"


class _MockIdpHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静音
        pass

    def _send(self, obj: dict, code: int = 200) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        m: MockIdp = self.server.mock
        path = self.path.split("?")[0]
        if path == f"{PREFIX}/.well-known/openid-configuration":
            self._send(
                {
                    "issuer": m.issuer,
                    "authorization_endpoint": f"{m.issuer}/authorize",
                    "token_endpoint": f"{m.issuer}/token",
                    "jwks_uri": f"{m.issuer}/jwks",
                    "userinfo_endpoint": f"{m.issuer}/userinfo",
                    "token_endpoint_auth_methods_supported": ["client_secret_post"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                }
            )
        elif path == f"{PREFIX}/jwks":
            self._send(m.jwks)
        elif path == f"{PREFIX}/userinfo":
            self._send(m.claims)
        elif path == f"{PREFIX}/authorize":
            q = parse_qs(urlparse(self.path).query)
            loc = f"{q.get('redirect_uri', [''])[0]}?{urlencode({'code': 'mock-code-1', 'state': q.get('state', [''])[0]})}"
            self.send_response(302)
            self.send_header("Location", loc)
            self.end_headers()
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        m: MockIdp = self.server.mock
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
        if path == f"{PREFIX}/token":
            ok = (
                form.get("grant_type") == "authorization_code"
                and form.get("code", "").startswith("mock-")
                and form.get("client_id") == CLIENT_ID
                and form.get("client_secret") == CLIENT_SECRET
            )
            if ok:
                self._send(
                    {
                        "id_token": m.sign_id_token(m.claims, form["client_id"]),
                        "access_token": "mock-access",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    }
                )
            else:
                self._send({"error": "invalid_grant"}, 400)
        else:
            self._send({"error": "not found"}, 404)


@pytest.fixture
def mock_idp():
    m = MockIdp()
    m.start()
    yield m
    m.stop()


@pytest.fixture
def sso_app(db, mock_idp):
    return SocialApp.objects.create(
        provider="openid_connect",
        provider_id="oidc",
        name="SSO",
        client_id=CLIENT_ID,
        secret=CLIENT_SECRET,
        settings={"server_url": mock_idp.issuer},
    )


def full_sso_login(client: Client) -> None:
    """bridge 302 → allauth login 302 → (模拟 IdP 回跳) callback → 登录成功 302。"""
    r1 = client.get("/api/v1/auth/oidc/login", {"next": "/sso/callback"})
    assert r1.status_code == 302, r1.content[:200]
    r2 = client.get(r1["Location"])
    assert r2.status_code == 302, r2.content[:300]
    q = parse_qs(urlparse(r2["Location"]).query)
    redirect_uri = q["redirect_uri"][0]
    state = q["state"][0]
    r3 = client.get(f"{redirect_uri}?{urlencode({'code': 'mock-code-1', 'state': state})}")
    assert r3.status_code == 302, r3.content[:500]
    assert quote("/sso/callback") in r3["Location"] or "/sso/callback" in r3["Location"]


class SsoConfigTest:
    def test_config_enabled(self, db):
        r = Client().get("/api/v1/auth/config")
        assert r.status_code == 200
        assert r.json() == {"sso_enabled": True}

    @override_settings(OIDC_ENABLED=False)
    def test_disabled(self, db):
        assert Client().get("/api/v1/auth/config").json() == {"sso_enabled": False}
        # 未启用时登录桥 404
        assert Client().get("/api/v1/auth/oidc/login").status_code == 404


class SsoFlowTest:
    def test_full_flow_creates_operator(self, db, sso_app):
        client = Client()
        full_sso_login(client)
        u = User.objects.get(username="ssouser")
        assert u.role == User.Role.OPERATOR
        assert u.must_change_password is False
        assert not u.has_usable_password()  # 本地密码未设（可自助设置）
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["username"] == "ssouser"

    @override_settings(OIDC_ROLE_MAP=json.dumps({"groups": {"recon-admin": "admin"}}))
    def test_role_mapping(self, db, sso_app, mock_idp):
        mock_idp.claims["groups"] = ["recon-admin"]
        client = Client()
        full_sso_login(client)
        assert User.objects.get(username="ssouser").role == User.Role.ADMIN

    def test_bind_existing_user(self, db, sso_app):
        # 本地已有同名账号（admin，有密码）→ SSO 登录绑定之，角色不变、不重复建号
        admin = User.objects.create_user(
            "ssouser", password="Op@12345", role=User.Role.ADMIN, must_change_password=False
        )
        client = Client()
        full_sso_login(client)
        assert User.objects.filter(username="ssouser").count() == 1
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["id"] == admin.id
        assert me.json()["role"] == "admin"
