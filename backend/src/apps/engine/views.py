"""对账运行 API：触发（202/409）、列表。"""
from __future__ import annotations

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.errors import BusinessRuleError, NotFoundError
from apps.core.permissions import IsAdminOrOperator
from apps.engine import control
from apps.engine.models import ReconcileRun


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
