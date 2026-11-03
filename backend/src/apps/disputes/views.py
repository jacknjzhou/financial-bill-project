"""差错 API：列表筛选 / 处理 / 留痕时间线。"""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.errors import BusinessRuleError, ValidationError
from apps.core.permissions import IsAdminOrOperator
from apps.disputes.models import Dispute, HandleLog


class DisputeSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    dispute_type_name = serializers.CharField(source="dispute_type.name", read_only=True, default="")
    handler_name = serializers.CharField(source="handler.username", read_only=True, default="")
    amount_yuan = serializers.SerializerMethodField()
    order_no = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = [
            "id", "project", "project_name", "reconcile_date", "type",
            "a", "b", "order_no", "amount", "amount_yuan", "status",
            "dispute_type", "dispute_type_name", "handler", "handler_name",
            "handled_at", "remark", "superseded", "group_no", "created_at",
        ]

    def get_amount_yuan(self, obj) -> str:
        return f"{obj.amount / 100:.2f}"

    def get_order_no(self, obj) -> str:
        if obj.a_id:
            return obj.a.order_no
        if obj.b_id:
            return obj.b.order_no or obj.b.channel_order_no
        return ""


class HandleSerializer(serializers.Serializer):
    dispute_type_id = serializers.IntegerField()
    remark = serializers.CharField(allow_blank=False, required=True)
    to_processing = serializers.BooleanField(required=False, default=False, help_text="true 仅转处理中，false 直接完成处理")


class LogSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source="operator.username", read_only=True, default="")

    class Meta:
        model = HandleLog
        fields = ["id", "action", "operator", "operator_name", "from_status", "to_status", "remark", "created_at"]


class DisputeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Dispute.objects.select_related("project", "dispute_type", "handler", "a", "b").all()
    serializer_class = DisputeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if v := p.get("project"):
            qs = qs.filter(project_id=v)
        if v := p.get("reconcile_date"):
            qs = qs.filter(reconcile_date=v)
        if v := p.get("status"):
            qs = qs.filter(status=v)
        if v := p.get("type"):
            qs = qs.filter(type=v)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("project", int, "query"),
            OpenApiParameter("reconcile_date", str, "query"),
            OpenApiParameter("status", str, "query", description="open/processing/closed"),
            OpenApiParameter("type", str, "query", description="one_a/one_b/wrong"),
        ],
        summary="差错列表（分页筛选）",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=HandleSerializer, responses={200: DisputeSerializer, 400: None, 409: None}, summary="处理差错（open→processing→closed）")
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsAdminOrOperator])
    def handle(self, request, pk=None):
        dispute = self.get_object()
        if dispute.status == Dispute.Status.CLOSED:
            raise BusinessRuleError("该差异已处理完成", code="ALREADY_CLOSED")

        ser = HandleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        remark = ser.validated_data["remark"].strip()
        if not remark:
            raise ValidationError("处理备注为必填项")

        from apps.meta.models import DisputeType

        dtype = DisputeType.objects.filter(pk=ser.validated_data["dispute_type_id"]).first()
        if dtype is None:
            raise ValidationError("差错处理类型不存在")
        # 分组匹配：交易型差异只能选 TRANSACTION 组 SOP（资金型留二期扩展）
        if dispute.type in (Dispute.Type.ONE_A, Dispute.Type.ONE_B, Dispute.Type.WRONG):
            if dtype.group != "TRANSACTION":
                raise ValidationError(f"处理类型分组不符：交易差异需选交易组 SOP（{dtype.name} 属于 {dtype.group}）")

        to_status = Dispute.Status.PROCESSING if ser.validated_data["to_processing"] else Dispute.Status.CLOSED
        from_status = dispute.status
        dispute.status = to_status
        dispute.dispute_type = dtype
        dispute.remark = remark
        if to_status == Dispute.Status.CLOSED:
            dispute.handler = request.user
            dispute.handled_at = timezone.now()
        dispute.save()

        HandleLog.objects.create(
            dispute=dispute,
            action=HandleLog.Action.PROCESSING if to_status == Dispute.Status.PROCESSING else HandleLog.Action.HANDLED,
            operator=request.user,
            from_status=from_status,
            to_status=to_status,
            remark=remark,
        )
        return Response(DisputeSerializer(dispute).data)

    @extend_schema(responses={200: LogSerializer(many=True)}, summary="处理留痕（时间线倒序）")
    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        dispute = self.get_object()
        logs = dispute.logs.select_related("operator").all()
        return Response({"total": logs.count(), "items": LogSerializer(logs, many=True).data})
