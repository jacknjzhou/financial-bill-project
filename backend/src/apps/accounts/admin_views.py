"""用户管理（系统管理）：admin 限定 CRUD + 自我保护 + 密码重置。"""
from django.contrib.auth import update_session_auth_hash  # noqa: F401
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.errors import BusinessRuleError, ValidationError
from apps.core.permissions import IsAdmin
from apps.core.schema import crud_schema

from .models import User


class UserAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "role", "must_change_password", "is_active", "created_at"]
        read_only_fields = ["must_change_password", "created_at"]

    def validate_username(self, value: str) -> str:
        qs = User.objects.filter(username=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("用户名已存在")
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        if password and self.instance is None:
            try:
                validate_password(password)
            except DjangoValidationError as e:
                raise ValidationError({"password": list(e.messages)})
        return attrs


class UserAdminSerializerWithPassword(UserAdminSerializer):
    class Meta(UserAdminSerializer.Meta):
        fields = ["id", "username", "password", "role", "must_change_password", "is_active", "created_at"]
        extra_kwargs = {"password": {"write_only": True, "required": True}}

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.must_change_password = True  # 初始密码首次登录强制修改
        user.save()
        return user


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=8, max_length=64)


@crud_schema(UserAdminSerializerWithPassword, "User")
class UserAdminViewSet(viewsets.ModelViewSet):
    """仅 admin 可见可写（operator 一律 403）。"""

    queryset = User.objects.all().order_by("id")
    serializer_class = UserAdminSerializerWithPassword
    permission_classes = [IsAuthenticated, IsAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        if v := self.request.query_params.get("role"):
            qs = qs.filter(role=v)
        if v := self.request.query_params.get("username"):
            qs = qs.filter(username__contains=v)
        return qs

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise BusinessRuleError("不能操作当前登录账号", code="SELF_PROTECTED")
        instance.delete()

    def perform_update(self, serializer):
        # 自我保护先于落库：停用/降级当前登录账号直接 409
        if serializer.instance.pk == self.request.user.pk:
            data = serializer.validated_data
            if data.get("is_active") is False:
                raise BusinessRuleError("不能停用当前登录账号", code="SELF_PROTECTED")
            if data.get("role") and data["role"] != self.request.user.role:
                raise BusinessRuleError("不能修改当前登录账号的角色", code="SELF_PROTECTED")
        serializer.save()

    @extend_schema(request=ResetPasswordSerializer, responses={200: None, 400: None}, summary="重置本地密码（admin）")
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        ser = ResetPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_password = ser.validated_data["new_password"]
        try:
            validate_password(new_password)
        except DjangoValidationError as e:
            raise ValidationError({"new_password": list(e.messages)})
        user.set_password(new_password)
        user.must_change_password = True  # 重置后强制改密
        user.save(update_fields=["password", "must_change_password"])
        return Response({"ok": True})
