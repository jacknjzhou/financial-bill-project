"""解析规则（仅 admin 可写，规格约束）/ 获取任务 / 对账项目。"""
from apps.core.permissions import IsAdmin, IsAdminOrOperator
from apps.core.schema import crud_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import FetchTask, ParseRule, ReconcileProject
from .serializers import FetchTaskSerializer, ParseRuleSerializer, ReconcileProjectSerializer


@crud_schema(ParseRuleSerializer, "ParseRule")
class ParseRuleViewSet(viewsets.ModelViewSet):
    queryset = ParseRule.objects.all()
    serializer_class = ParseRuleSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOperator]

    def get_permissions(self):
        # 规格：operator 无「解析规则」写权限
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()


@crud_schema(FetchTaskSerializer, "FetchTask")
class FetchTaskViewSet(viewsets.ModelViewSet):
    queryset = FetchTask.objects.select_related("channel", "account", "parse_rule")
    serializer_class = FetchTaskSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOperator]


@crud_schema(ReconcileProjectSerializer, "ReconcileProject")
class ReconcileProjectViewSet(viewsets.ModelViewSet):
    queryset = ReconcileProject.objects.prefetch_related("alert_users")
    serializer_class = ReconcileProjectSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOperator]
