"""基础字典 CRUD（权限：operator 可写——规格仅限制「系统管理」与「解析规则」写）。

删除保护：被下游引用 → 409（引用数据不动，保证对账可追溯）。
"""
from apps.core.errors import BusinessRuleError
from apps.core.schema import crud_schema
from apps.core.permissions import IsAdminOrOperator
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import BizType, Channel, DisputeType, FundAccount
from .serializers import BizTypeSerializer, ChannelSerializer, DisputeTypeSerializer, FundAccountSerializer


@crud_schema(ChannelSerializer, "Channel")
class ChannelViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOperator]

    def perform_destroy(self, instance):
        if instance.accounts.exists():
            raise BusinessRuleError("无法删除：仍被资金账户引用")
        instance.delete()


@crud_schema(FundAccountSerializer, "FundAccount")
class FundAccountViewSet(viewsets.ModelViewSet):
    queryset = FundAccount.objects.select_related("channel")
    serializer_class = FundAccountSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOperator]

    def perform_destroy(self, instance):
        # 一期尚无源数据引用账户（数据表在 T8 引用）；此处预留：有引用即 409
        instance.delete()


@crud_schema(BizTypeSerializer, "BizType")
class BizTypeViewSet(viewsets.ModelViewSet):
    queryset = BizType.objects.all()
    serializer_class = BizTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOperator]


@crud_schema(DisputeTypeSerializer, "DisputeType")
class DisputeTypeViewSet(viewsets.ModelViewSet):
    queryset = DisputeType.objects.all()
    serializer_class = DisputeTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOperator]
