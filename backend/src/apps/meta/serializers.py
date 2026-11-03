from rest_framework import serializers

from .models import BizType, Channel, DisputeType, FundAccount


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = ["id", "code", "name", "enabled", "created_at", "updated_at"]


class FundAccountSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True)
    # start_balance：模型层 BigIntegerField → schema 自动映射 int64（单位：分）
    # start_date：模型层 DateField → schema ISO 日期

    class Meta:
        model = FundAccount
        fields = [
            "id", "channel", "channel_name", "name", "account_no",
            "start_date", "start_balance", "enabled", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        # 启用日期 + 启用余额必填（模型层也必填，这里给出指向明确的错误）
        for f in ("start_date", "start_balance"):
            if f in attrs and attrs[f] in (None, ""):
                raise serializers.ValidationError({f: "该字段为必填项"})
        return attrs


class BizTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BizType
        fields = ["id", "code", "name", "group", "created_at", "updated_at"]


class DisputeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeType
        fields = ["id", "group", "name", "description", "created_at", "updated_at"]
