from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers

from apps.core.errors import NotFoundError, ValidationError

from .models import User  # noqa: F401
from .oidc import PROVIDER, get_or_create_sso_app, sso_provider_id
from .serializers import (
    AuthConfigSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    OkSerializer,
    UserOutSerializer,
)

# 注意：@api_view 只拷贝 func 上的 schema 属性，extend_schema 必须放在
# api_view 外层（drf-spectacular 对带 .cls 的 as_view() 产物有专门分支）。

LoginRespSerializer = inline_serializer(
    "LoginResp",
    fields={
        "user": UserOutSerializer(),
        "must_change_password": serializers.BooleanField(),
    },
)


@extend_schema(
    request=LoginSerializer,
    responses={200: LoginRespSerializer, 400: None},
    summary="账号密码登录",
)
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """账号密码登录（两种登录模式之一；SSO 见 T2B）。成功后建 Django 会话。"""
    ser = LoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = authenticate(
        request,
        username=ser.validated_data["username"],
        password=ser.validated_data["password"],
    )
    if user is None or not user.is_active:
        # 统一文案，不泄漏账号是否存在 / 是否停用
        raise ValidationError("用户名或密码错误", code="INVALID_CREDENTIALS")
    login(request, user)
    return Response(
        {"user": UserOutSerializer(user).data, "must_change_password": user.must_change_password}
    )


@extend_schema(responses={200: OkSerializer}, summary="登出")
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({"ok": True})


@extend_schema(responses={200: UserOutSerializer}, summary="当前登录用户")
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserOutSerializer(request.user).data)


@extend_schema(
    request=ChangePasswordSerializer,
    responses={200: OkSerializer, 400: None},
    summary="修改/设置本地密码（未设密码免旧密码）",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """改密；未设密码（SSO 建号）免旧密码。成功后 must_change_password 转 False。"""
    ser = ChangePasswordSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = request.user
    old = ser.validated_data.get("old_password") or ""
    new = ser.validated_data["new_password"]
    if user.has_usable_password():
        if not old or not user.check_password(old):
            raise ValidationError("旧密码不正确", code="INVALID_CREDENTIALS")
    if user.has_usable_password() and user.check_password(new):
        raise ValidationError("新密码不能与旧密码相同")
    user.set_password(new)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password"])
    # 关键：密码变更会使会话认证哈希失配（Django 会登出该会话），
    # 轮换会话哈希保持当前会话有效——强制改密流程改完不能把用户踢回登录页
    update_session_auth_hash(request, user)
    return Response({"ok": True})


@extend_schema(responses={200: OkSerializer}, summary="种 csrftoken cookie")
@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_view(request):
    """前端首个 POST 前调用，种 csrftoken cookie。"""
    return Response({"ok": True})


@extend_schema(responses={200: AuthConfigSerializer}, summary="登录页配置（SSO 开关）")
@api_view(["GET"])
@permission_classes([AllowAny])
def auth_config_view(request):
    """登录页配置：是否展示 SSO 按钮。"""
    return Response({"sso_enabled": bool(getattr(settings, "OIDC_ENABLED", False))})


@extend_schema(
    parameters=[
        OpenApiParameter(name="next", type=str, description="登录成功后回跳的前端路径", default="/")
    ],
    responses={302: OpenApiResponse(response=None), 404: OpenApiResponse(response=None)},
    summary="SSO 登录桥（302 至 IdP）",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def oidc_login_view(request):
    """SSO 登录桥：302 至 allauth 的 OIDC 登录 URL（随后 302 至企业 IdP）。"""
    if not getattr(settings, "OIDC_ENABLED", False):
        raise NotFoundError("SSO 未启用")
    get_or_create_sso_app()
    from urllib.parse import urlencode

    next_url = request.query_params.get("next") or "/"
    url = reverse(f"{PROVIDER}_login", kwargs={"provider_id": sso_provider_id()})
    return redirect(f"{url}?{urlencode({'process': 'login', 'next': next_url})}")
