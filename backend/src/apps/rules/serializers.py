from rest_framework import serializers

from apps.accounts.models import User

from .models import STANDARD_FIELDS, FetchTask, ParseRule, ReconcileProject


class ParseRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParseRule
        fields = [
            "id", "name", "target", "file_format", "encoding", "delimiter", "header_row",
            "column_map", "value_maps", "amount_scale", "time_format",
            "created_at", "updated_at",
        ]

    def validate_column_map(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError("column_map 必须是对象")
        mapped = {k: v for k, v in value.items() if k and v}
        if not mapped:
            raise serializers.ValidationError("至少映射一个字段")
        for col, field in mapped.items():
            if field not in STANDARD_FIELDS:
                raise serializers.ValidationError(f"列「{col}」映射到未知标准字段「{field}」")
        return value

    def validate_value_maps(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError("value_maps 必须是对象")
        for field, mapping in value.items():
            if field not in STANDARD_FIELDS:
                raise serializers.ValidationError(f"value_maps 含未知标准字段「{field}」")
            if not isinstance(mapping, dict):
                raise serializers.ValidationError(f"value_maps[{field}] 必须是对象")
        return value

    def validate_amount_scale(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("amount_scale 必须为正整数")
        return value


class FetchTaskSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True, default=None)
    account_name = serializers.CharField(source="account.name", read_only=True, default=None)
    parse_rule_name = serializers.CharField(source="parse_rule.name", read_only=True)

    class Meta:
        model = FetchTask
        fields = [
            "id", "name", "side", "channel", "channel_name", "account", "account_name",
            "parse_rule", "parse_rule_name", "mode", "created_at", "updated_at",
        ]


class ReconcileProjectSerializer(serializers.ModelSerializer):
    # 显式类型化：JSONField 默认渲染为泛型 object，规格要求"带完整 schema"
    a_filter = serializers.ListField(child=serializers.DictField(), required=False, help_text='条件组：[{"field","op"(eq/in/neq),"value"}]')
    b_filter = serializers.ListField(child=serializers.DictField(), required=False, help_text="同 a_filter")
    a_status_set = serializers.ListField(child=serializers.CharField(), required=False, help_text='A 方期望状态集，如 ["SUCCESS"]')
    b_status_set = serializers.ListField(child=serializers.CharField(), required=False, help_text="B 方期望状态集")

    class Meta:
        model = ReconcileProject
        fields = [
            "id", "name", "type", "a_source", "a_filter", "b_source", "b_filter",
            "match_key", "a_status_set", "b_status_set", "b_sum",
            "start_date", "last_date", "exec_time", "alert_users", "enabled",
            "created_at", "updated_at",
        ]

    def validate(self, attrs):
        ptype = attrs.get("type", getattr(self.instance, "type", None))
        a_source = attrs.get("a_source", getattr(self.instance, "a_source", None))
        b_source = attrs.get("b_source", getattr(self.instance, "b_source", None))

        combos = {
            "transaction": [("payment", "clearing")],
            "fund": [("clearing", "settlement")],
            "balance": [],
        }
        allowed = combos.get(ptype)
        if allowed is None:
            raise serializers.ValidationError({"type": "未知对账类型"})
        if not allowed or (a_source, b_source) not in allowed:
            raise serializers.ValidationError(
                {"type": f"类型 {ptype} 的 A/B 数据源组合 {(a_source, b_source)} 不允许（允许：{allowed}）"}
            )

        match_key = attrs.get("match_key", getattr(self.instance, "match_key", "order_no"))
        if match_key not in STANDARD_FIELDS:
            raise serializers.ValidationError({"match_key": f"匹配键「{match_key}」不是标准字段"})

        for name in ("a_filter", "b_filter"):
            flt = attrs.get(name)
            if flt is None:
                continue
            if not isinstance(flt, list):
                raise serializers.ValidationError({name: "筛选条件必须是数组"})
            for cond in flt:
                if not isinstance(cond, dict) or cond.get("field") not in STANDARD_FIELDS:
                    raise serializers.ValidationError({name: f"筛选条件字段未知或不合法：{cond}"})
                if cond.get("op") not in ("eq", "in", "neq"):
                    raise serializers.ValidationError({name: f"筛选操作只支持 eq/in/neq：{cond}"})

        for name in ("a_status_set", "b_status_set"):
            ss = attrs.get(name)
            if ss is not None and not isinstance(ss, list):
                raise serializers.ValidationError({name: "状态集必须是字符串数组"})

        # 防历史空洞：一旦已有对账进度，不得把启用日期改到最后对账日期之前
        new_start = attrs.get("start_date")
        new_last = attrs.get("last_date", getattr(self.instance, "last_date", None))
        if new_start and new_last and new_start < new_last:
            raise serializers.ValidationError(
                {"start_date": "启用日期不得早于最后对账日期（会产生历史对账空洞）"}
            )
        return attrs

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)
        # alert_users：接受 id 数组
        if "alert_users" in data and isinstance(data["alert_users"], list):
            ret["alert_users_ids"] = data["alert_users"]
        return ret

    def create(self, validated_data):
        ids = validated_data.pop("alert_users_ids", None)
        obj = super().create(validated_data)
        if ids is not None:
            obj.alert_users.set(User.objects.filter(id__in=ids))
        return obj

    def update(self, instance, validated_data):
        ids = validated_data.pop("alert_users_ids", None)
        obj = super().update(instance, validated_data)
        if ids is not None:
            obj.alert_users.set(User.objects.filter(id__in=ids))
        return obj
