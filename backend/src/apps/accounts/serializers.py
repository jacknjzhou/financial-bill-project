from rest_framework import serializers

from .models import User


class UserOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "role", "must_change_password", "is_active", "created_at"]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    # 未设密码（SSO 自动建号用户）免旧密码
    old_password = serializers.CharField(required=False, allow_blank=True)
    new_password = serializers.CharField(min_length=8, max_length=64)
