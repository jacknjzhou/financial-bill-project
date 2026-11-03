"""对账运行 API：触发（202/409）、列表。"""
from __future__ import annotations

from django.db import transaction
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.errors import BusinessRuleError, NotFoundError
from apps.core.permissions import IsAdminOrOperator
from apps.engine import control
from apps.engine.models import Alert, ReconcileResult, ReconcileRun


class RunSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    triggered_by_name = serializers.CharField(source="triggered_by.username", read_only=True, default="")

    class Meta:
        model = ReconcileRun
        fields = [
            "id", "project", "project_name", "reconcile_date", "status",
            "a_total", "b_total", "match_cnt", "one_a_cnt", "one_b_cnt", "wrong_cnt",
            "trigger", "triggered_by", "triggered_by_name",
            "started_at", "finished_at", "error", "created_at",
        ]


class TriggerRunSerializer(serializers.Serializer):
    date = serializers.DateField(required=False, help_text="对账日期，默认今天-1")
    rerun = serializers.BooleanField(required=False, default=False)


class RunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReconcileRun.objects.select_related("project", "triggered_by").all()
    serializer_class = RunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if v := p.get("project"):
            qs = qs.filter(project_id=v)
        if v := p.get("status"):
            qs = qs.filter(status=v)
        if v := p.get("reconcile_date"):
            qs = qs.filter(reconcile_date=v)
        return qs

    @extend_schema(responses={200: RunSerializer(many=True)}, summary="对账运行列表")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminOrOperator])
@extend_schema(
    request=TriggerRunSerializer,
    responses={202: {"type": "object", "properties": {"run_id": {"type": "integer"}}}, 409: None},
    summary="触发对账（date 默认今天-1；rerun=true 走重对，跳过连续性）",
)
def trigger_run_view(request, project_id: int):
    from apps.rules.models import ReconcileProject

    project = ReconcileProject.objects.filter(pk=project_id, enabled=True).first()
    if project is None:
        raise NotFoundError("对账项目不存在或已停用")

    raw_date = request.data.get("date")
    if raw_date:
        try:
            from datetime import date as date_cls

            date = date_cls.fromisoformat(str(raw_date))
        except ValueError:
            raise BusinessRuleError(f"日期格式不合法：{raw_date}（期望 YYYY-MM-DD）")
    else:
        date = control.default_reconcile_date()
    rerun = bool(request.data.get("rerun"))
    trigger = ReconcileRun.Trigger.RERUN if rerun else ReconcileRun.Trigger.MANUAL

    run, ok, reason = control.create_run(project, date, trigger, user=request.user)
    if not ok:
        raise BusinessRuleError(reason, code="CANNOT_RUN")

    transaction.on_commit(lambda: _delay_run(run.id))
    return Response({"run_id": run.id, "status": run.status}, status=202)


def _delay_run(run_id: int) -> None:
    from apps.engine.tasks import run_reconcile

    run_reconcile.delay(run_id)


# ---------- 对账结果查询 ----------

class ResultSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    diff_amount_yuan = serializers.SerializerMethodField()
    order_no = serializers.SerializerMethodField()

    class Meta:
        model = ReconcileResult
        fields = [
            "id", "run", "project", "project_name", "reconcile_date", "status",
            "a", "b", "order_no", "match_key", "diff_amount", "diff_amount_yuan",
            "diff_type", "group_no", "biz_type", "created_at",
        ]

    def get_diff_amount_yuan(self, obj) -> str:
        return f"{obj.diff_amount / 100:.2f}"

    def get_order_no(self, obj) -> str:
        if obj.a_id:
            return obj.a.order_no
        if obj.b_id:
            return obj.b.order_no or obj.b.channel_order_no
        return obj.match_key


class ResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReconcileResult.objects.select_related("a", "b", "project", "biz_type").all()
    serializer_class = ResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if v := p.get("project"):
            qs = qs.filter(project_id=v)
        if v := p.get("date"):
            qs = qs.filter(reconcile_date=v)
        if v := p.get("reconcile_date"):
            qs = qs.filter(reconcile_date=v)
        if v := p.get("status"):
            qs = qs.filter(status=v)
        return qs

    @extend_schema(responses={200: ResultSerializer(many=True)}, summary="对账结果列表（分页）")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        responses={
            200: inline_serializer(
                "ResultDetail",
                fields={
                    "result": ResultSerializer(),
                    "a_row": serializers.JSONField(required=False, allow_null=True, help_text="A 方源数据全字段"),
                    "b_rows": serializers.ListField(
                        child=serializers.JSONField(), required=False, help_text="同组 B 方源数据全字段（可追溯）"
                    ),
                },
            )
        },
        summary="结果详情：A 原文 + 同组全部 B 原文（可追溯性）",
    )
    def retrieve(self, request, *args, **kwargs):
        result = self.get_object()
        a_row = None
        if result.a_id:
            a_row = _model_full(result.a)
        b_rows = []
        if result.b_id:
            siblings = type(result).objects.filter(group_no=result.group_no, b__isnull=False).select_related("b")
            b_rows = [_model_full(r.b) for r in siblings]
        elif result.a_id:
            # A 侧组（1vN）：同组 B 行取回
            siblings = type(result).objects.filter(group_no=result.group_no, b__isnull=False).select_related("b")
            b_rows = [_model_full(r.b) for r in siblings]
        ser = ResultSerializer(result)
        return Response({"result": ser.data, "a_row": a_row, "b_rows": b_rows})


def _model_full(obj) -> dict:
    """源数据全字段（可追溯）：字段名 → 值；金额附 _yuan 展示。"""
    from django.forms.models import model_to_dict

    data = {"id": obj.pk}
    for field in obj._meta.concrete_fields:
        if field.attname in ("storage_path",):
            continue  # 不暴露存储路径
        value = getattr(obj, field.name)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif hasattr(value, "pk"):
            value = value.pk
        data[field.name] = value
        if field.name == "amount" and value is not None:
            data["amount_yuan"] = f"{value / 100:.2f}"
    # model_to_dict 仅为兼容保留引用
    _ = model_to_dict
    return data


# ---------- 工作台与告警（T13） ----------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@extend_schema(
    responses={
        200: inline_serializer(
            "DashboardOverview",
            fields={
                "reconcile_date": serializers.DateField(),
                "runs": serializers.ListField(child=serializers.JSONField()),
                "pending_disputes": serializers.IntegerField(),
                "alerts_unread": serializers.IntegerField(),
                "failed_runs": serializers.ListField(child=serializers.JSONField()),
            },
        )
    },
    summary="工作台总览（单查询聚合）",
)
def dashboard_overview_view(request):
    from django.db.models import Count, Q

    from apps.disputes.models import Dispute

    reconcile_date = control.default_reconcile_date()
    runs = (
        ReconcileRun.objects.filter(reconcile_date=reconcile_date)
        .select_related("project")
        .order_by("project_id")
    )
    pending_disputes = Dispute.objects.filter(status=Dispute.Status.OPEN).count()
    alerts_unread = Alert.objects.filter(read=False).count()
    failed_runs = (
        ReconcileRun.objects.filter(status=ReconcileRun.Status.FAILED)
        .select_related("project")
        .order_by("-id")[:10]
    )
    return Response(
        {
            "reconcile_date": reconcile_date.isoformat(),
            "runs": RunSerializer(runs, many=True).data,
            "pending_disputes": pending_disputes,
            "alerts_unread": alerts_unread,
            "failed_runs": RunSerializer(failed_runs, many=True).data,
        }
    )


class AlertSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Alert
        fields = ["id", "project", "project_name", "reconcile_date", "kind", "message", "read", "created_at"]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@extend_schema(responses={200: AlertSerializer(many=True)}, summary="未读告警列表")
def alerts_list_view(request):
    alerts = Alert.objects.select_related("project").order_by("-id")[:50]
    if request.query_params.get("all"):
        pass
    else:
        alerts = alerts.filter(read=False)
    return Response(AlertSerializer(alerts, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@extend_schema(responses={200: {"type": "object", "properties": {"ok": {"type": "boolean"}}}}, summary="标记告警已读（id 或全部）")
def alerts_read_view(request):
    alert_id = request.data.get("id")
    qs = Alert.objects.all()
    if alert_id:
        qs = qs.filter(pk=alert_id)
    updated = qs.filter(read=False).update(read=True)
    return Response({"ok": True, "updated": updated})
