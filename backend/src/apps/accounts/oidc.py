"""SSO / OIDC（allauth 65.x openid_connect 客户端）。

浏览器流程（env 开关 OIDC_ENABLED）：
  登录页「SSO 登录」→ GET /api/v1/auth/oidc/login（本模块桥）
  → 302 /accounts/{provider_id}/login/（allauth，发起 authorize 302 至企业 IdP）
  → IdP 认证后回跳 /accounts/{provider_id}/login/callback/（allauth 兑换 code、
    验 JWKS id_token）→ 建/绑用户 → Django 会话 → 302 前端 /sso/callback。

用户映射规则（用户钉死）：
- 首次 SSO 登录自动建号：username = preferred_username（缺则 email 本地段），
  角色按 OIDC_ROLE_MAP（claim → 角色 JSON）映射，默认 operator，
  本地密码未设（之后可自助设置或 admin 重置），must_change_password=False。
- 本地已有同 username 账号 → 直接绑定（角色保持原样）。
"""
import json
import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger(__name__)

PROVIDER = "openid_connect"


def sso_provider_id() -> str:
    from django.conf import settings

    return getattr(settings, "OIDC_PROVIDER_ID", "oidc")


def get_or_create_sso_app():
    """从 env 驱动创建/更新 SocialApp（幂等）。SSO 未启用返回 None。

    只写 env 中实际配置了值的字段——避免用空值覆盖已有配置
    （例如测试夹具预置了 server_url 而 env 未配 issuer 时）。
    """
    from django.conf import settings

    if not getattr(settings, "OIDC_ENABLED", False):
        return None
    from allauth.socialaccount.models import SocialApp

    issuer = getattr(settings, "OIDC_ISSUER", "")
    app = SocialApp.objects.filter(provider=PROVIDER, provider_id=sso_provider_id()).first()
    if app is None:
        if not issuer:
            return None  # SSO 已启用但未配置 IdP：不建残缺 app
        app = SocialApp.objects.create(
            provider=PROVIDER,
            provider_id=sso_provider_id(),
            name="SSO",
            client_id=getattr(settings, "OIDC_CLIENT_ID", ""),
            secret=getattr(settings, "OIDC_CLIENT_SECRET", ""),
            settings={"server_url": issuer},
        )
        return app
    changed = False
    if getattr(settings, "OIDC_CLIENT_ID", ""):
        app.client_id = settings.OIDC_CLIENT_ID
        changed = True
    if getattr(settings, "OIDC_CLIENT_SECRET", ""):
        app.secret = settings.OIDC_CLIENT_SECRET
        changed = True
    if issuer:
        app.settings = {**(app.settings or {}), "server_url": issuer}
        changed = True
    if changed:
        app.save()
    return app


def user_claims(sociallogin) -> dict:
    """归一化 IdP claims：allauth OIDC 的 extra_data 形如
    {"userinfo": {...}, "id_token": {...}}，合并各层供映射使用。"""
    extra = sociallogin.account.extra_data or {}
    claims: dict = {}
    for part in (extra.get("userinfo"), extra.get("id_token"), extra):
        if isinstance(part, dict):
            claims.update(part)
    return claims


def role_from_claims(data: dict) -> str:
    """按 OIDC_ROLE_MAP（{"claim": {取值: 角色}}）映射角色；未命中 → operator。"""
    from django.conf import settings
    from apps.accounts.models import User

    try:
        role_map = json.loads(getattr(settings, "OIDC_ROLE_MAP", "{}") or "{}")
    except (json.JSONDecodeError, TypeError):
        logger.warning("OIDC_ROLE_MAP 不是合法 JSON，忽略")
        return User.Role.OPERATOR
    for claim, mapping in role_map.items():
        if not isinstance(mapping, dict):
            continue
        value = data.get(claim)
        values = value if isinstance(value, (list, tuple)) else [value]
        for v in values:
            if v is None:
                continue
            if v in mapping:
                return mapping[v]
            if str(v) in mapping:
                return mapping[str(v)]
    return User.Role.OPERATOR


class ReconSocialAccountAdapter(DefaultSocialAccountAdapter):
    """自动建号 + 角色映射 + 同名绑定。"""

    def is_open_for_signup(self, request, sociallogin) -> bool:
        # 首次 SSO 登录直接建号，不经过注册表单（内部系统）
        return True

    def save_user(self, request, sociallogin, form=None):
        """allauth 默认实现的副作用不符合本系统需求（set_unusable_password
        会清掉绑定用户的本地密码、username 会被重新生成），故自行落库。

        - 同名绑定：username 对应已有本地账号 → connect（角色/密码保持原样）
        - 新账号：username = preferred_username（缺则 email 本地段），
          角色按 OIDC_ROLE_MAP 映射，默认 operator，本地密码未设。
        """
        from apps.accounts.models import User

        extra = user_claims(sociallogin)
        email = sociallogin.user.email or extra.get("email") or ""
        username = (
            extra.get("preferred_username")
            or sociallogin.user.username
            or (email.split("@")[0] if email else "")
            or f"ssouser{sociallogin.account.uid}"
        )
        existing = User.objects.filter(username=username).first()
        if existing is not None:
            sociallogin.connect(request, existing)
            return existing
        user = sociallogin.user
        user.username = username
        if email:
            user.email = email
        user.role = role_from_claims(extra)
        user.must_change_password = False
        user.set_unusable_password()  # 本地密码未设，之后可自助设置或 admin 重置
        user.save()
        sociallogin.save(request)
        return user
