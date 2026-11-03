"""数据接入 API：上传（防重/覆盖/限额）、记录列表/下载、三源数据查询。"""
from __future__ import annotations

import uuid
from pathlib import Path

from django.apps import apps
from django.conf import settings as dj_settings
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.errors import BusinessRuleError, ValidationError
from apps.core.permissions import IsAdminOrOperator
from apps.dataio.models import ClearingData, InFile, PaymentData, SettlementData
from apps.dataio.tasks import parse_file_task

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
EXT_ALIASES = {"xlsx": {".xlsx"}, "csv": {".csv"}, "txt": {".txt", ".dat"}}


# ---------- serializers ----------

class InFileSerializer(serializers.ModelSerializer):
    fetch_task_name = serializers.CharField(source="fetch_task.name", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.username", read_only=True, default="")
    size_mb = serializers.SerializerMethodField()

    class Meta:
        model = InFile
        fields = [
            "id", "fetch_task", "fetch_task_name", "file_name", "size", "size_mb",
            "status", "total_rows", "failed_rows", "error_msg",
            "uploaded_by", "uploaded_by_name", "created_at", "created_date",
        ]

    def get_size_mb(self, obj) -> float:
        return round(obj.size / 1024 / 1024, 2)


# 文件记录列表端点的完整分页信封（函数视图不走 ViewSet 分页器自动包装）
InFileListPage = inline_serializer(
    "InFileListPage",
    fields={
        "total": serializers.IntegerField(),
        "page": serializers.IntegerField(),
        "page_size": serializers.IntegerField(),
        "items": InFileSerializer(many=True),
    },
)


class PaymentSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True, default="")
    biz_type_code = serializers.CharField(source="biz_type.code", read_only=True, default="")
    amount_yuan = serializers.SerializerMethodField()

    class Meta:
        model = PaymentData
        fields = [
            "id", "order_no", "pay_no", "channel", "channel_name",
            "biz_type", "biz_type_code", "amount", "amount_yuan", "status",
            "tx_time", "tx_date", "reconcile_date", "file",
        ]

    def get_amount_yuan(self, obj) -> str:
        return f"{obj.amount / 100:.2f}"


class ClearingSerializer(PaymentSerializer):
    class Meta(PaymentSerializer.Meta):
        model = ClearingData
        fields = [
            "id", "channel_order_no", "order_no", "channel", "channel_name",
            "biz_type", "biz_type_code", "amount", "amount_yuan", "status",
            "tx_time", "tx_date", "reconcile_date", "file",
        ]


class SettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SettlementData
        fields = [
            "id", "channel", "account", "fee_item", "amount", "fee_amount",
            "actual_amount", "settle_date", "reconcile_date", "file",
        ]


# ---------- helpers ----------

def _sanitize_name(name: str) -> str:
    """剥路径分隔符与不可见字符，只保留文件名本体。"""
    name = (name or "").replace("\\", "/").split("/")[-1]
    return "".join(c for c in name if c.isprintable()) or "upload.bin"


def _file_is_reconciled(in_file: InFile) -> bool:
    """该上传文件的源数据是否已被对账结果引用（覆盖重传保护，守住可追溯反目标）。"""
    if not apps.is_installed("apps.engine"):
        return False
    try:
        from apps.engine.models import ReconcileResult
    except LookupError:
        return False
    pay_ids = list(in_file.payment_rows.values_list("id", flat=True))
    clr_ids = list(in_file.clearing_rows.values_list("id", flat=True))
    if pay_ids and ReconcileResult.objects.filter(a_id__in=pay_ids).exists():
        return True
    return bool(clr_ids and ReconcileResult.objects.filter(b_id__in=clr_ids).exists())


def _create_in_file(task, safe_name: str, content: bytes, user, today) -> InFile:
    root = Path(dj_settings.FILES_ROOT) / str(task.id) / str(today)
    root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    (root / stored_name).write_bytes(content)
    return InFile.objects.create(
        fetch_task=task,
        file_name=safe_name,
        storage_path=str(root / stored_name),
        size=len(content),
        uploaded_by=user,
        status=InFile.Status.PENDING,
        created_date=today,
    )


# ---------- upload / download ----------

def _upload_file(request):
    """POST /files：operator 及以上。"""
    from django.utils import timezone

    from apps.rules.models import FetchTask

    task_id = request.data.get("fetch_task")
    upload = request.FILES.get("file")
    if not task_id or not upload:
        raise ValidationError("fetch_task 与 file 为必填项")
    task = FetchTask.objects.select_related("parse_rule").filter(pk=task_id).first()
    if task is None:
        raise ValidationError("获取任务不存在")

    content = upload.read()
    if len(content) > MAX_FILE_SIZE:
        raise ValidationError("文件超过 50MB 上限", code="FILE_TOO_LARGE")

    rule = task.parse_rule
    suffix = Path(upload.name).suffix.lower()
    if suffix not in EXT_ALIASES.get(rule.file_format, set()):
        raise ValidationError(f"文件扩展名与解析规则不匹配（期望 {rule.file_format}）", code="EXT_MISMATCH")

    today = timezone.localdate()
    safe_name = _sanitize_name(upload.name)
    overwrite = request.query_params.get("overwrite") == "true"

    if overwrite:
        old = InFile.objects.filter(fetch_task=task, file_name=safe_name, created_date=today).first()
        if old and _file_is_reconciled(old):
            raise BusinessRuleError("该文件数据已参与对账，禁止覆盖重传", code="ALREADY_RECONCILED")

    try:
        with transaction.atomic():
            if overwrite:
                # 未被对账引用才可能走到这里（上方已拦截）；清旧数据与旧记录
                old = InFile.objects.filter(fetch_task=task, file_name=safe_name, created_date=today).first()
                if old:
                    old.payment_rows.all().delete()
                    old.clearing_rows.all().delete()
                    old.settlement_rows.all().delete()
                    InFile.objects.filter(pk=old.pk).delete()
            in_file = _create_in_file(task, safe_name, content, request.user, today)
    except BusinessRuleError:
        raise
    except Exception as e:  # noqa: BLE001 —— 唯一约束冲突归一为 409
        if "uniq_infile_task_name_date" in str(e):
            raise BusinessRuleError("同名文件今日已上传（如需覆盖请使用覆盖重传）", code="DUPLICATE_FILE") from e
        raise

    # 事务提交后再投递解析任务（防真实 worker 读到未提交行）
    transaction.on_commit(lambda: parse_file_task.delay(in_file.id))
    # eager 模式（测试/单机）on_commit 已触发执行，刷新状态返回
    in_file.refresh_from_db()
    return Response(InFileSerializer(in_file).data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@extend_schema(responses={200: {}}, summary="下载原始上传文件")
def download_file_view(request, pk: int):
    in_file = InFile.objects.filter(pk=pk).first()
    if in_file is None:
        raise ValidationError("文件不存在")
    path = Path(in_file.storage_path)
    if not path.exists():
        raise ValidationError("文件已丢失（存储缺失）", code="FILE_MISSING")
    return FileResponse(path.open("rb"), as_attachment=True, filename=in_file.file_name)


# ---------- 文件记录 ----------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@extend_schema(
    methods=["POST"],
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "fetch_task": {"type": "integer", "description": "获取任务 ID"},
                "file": {"type": "string", "format": "binary"},
            },
            "required": ["fetch_task", "file"],
        }
    },
    responses={201: InFileSerializer, 400: None, 409: None},
    summary="上传账单文件（同任务同日同名 409；?overwrite=true 覆盖重传）",
)
@extend_schema(
    methods=["GET"],
    parameters=[
        OpenApiParameter("fetch_task", int, "query", description="按获取任务筛选"),
        OpenApiParameter("status", str, "query", description="pending/parsing/parsed/failed"),
        OpenApiParameter("page", int, "query"),
        OpenApiParameter("page_size", int, "query"),
    ],
    responses={200: InFileListPage},
    summary="上传文件记录（前端轮询解析状态）",
)
def files_collection_view(request):
    """GET /files 列表；POST /files 上传（operator 及以上）。"""
    if request.method == "POST":
        return _upload_file(request)
    return _files_list(request)

DATE_PARAMS = [
    OpenApiParameter("reconcile_date", str, "query", description="对账日期 YYYY-MM-DD"),
    OpenApiParameter("status", str, "query", description="状态"),
    OpenApiParameter("channel", int, "query", description="渠道 ID"),
    OpenApiParameter("page", int, "query"),
    OpenApiParameter("page_size", int, "query"),
]


def _files_list(request):
    qs = InFile.objects.select_related("fetch_task", "uploaded_by").order_by("-id")
    if v := request.query_params.get("fetch_task"):
        qs = qs.filter(fetch_task_id=v)
    if v := request.query_params.get("status"):
        qs = qs.filter(status=v)
    paginator = _SimplePaginator(qs, request)
    return Response(paginator.envelope(InFileSerializer))


class _SimplePaginator:
    """files 端点的轻量分页（信封与全局 ReconPagination 一致）。"""

    def __init__(self, qs, request):
        self.qs = qs
        page = max(1, int(request.query_params.get("page", 1) or 1))
        size = min(200, max(1, int(request.query_params.get("page_size", 20) or 20)))
        self.page, self.size = page, size

    def envelope(self, ser_cls):
        total = self.qs.count()
        start = (self.page - 1) * self.size
        rows = ser_cls(self.qs[start : start + self.size], many=True).data
        return {"total": total, "page": self.page, "page_size": self.size, "items": rows}


# ---------- 三源数据查询 ----------

class _DataQueryViewSet(viewsets.ReadOnlyModelViewSet):
    """三源数据只读查询（分页 + 日期/单号/状态/渠道筛选）。"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if v := params.get("reconcile_date"):
            qs = qs.filter(reconcile_date=v)
        if v := params.get("status"):
            qs = qs.filter(status=v)
        if v := params.get("channel"):
            qs = qs.filter(channel_id=v)
        for f in ("order_no", "channel_order_no", "pay_no"):
            if v := params.get(f):
                qs = qs.filter(**{f"{f}__contains": v})
        return qs


@extend_schema(
    parameters=DATE_PARAMS + [OpenApiParameter("order_no", str, "query", description="商户单号（模糊）")],
    summary="自有支付流水查询",
)
class PaymentQueryViewSet(_DataQueryViewSet):
    queryset = PaymentData.objects.select_related("channel", "biz_type", "file").all()
    serializer_class = PaymentSerializer


@extend_schema(
    parameters=DATE_PARAMS + [OpenApiParameter("channel_order_no", str, "query", description="渠道单号（模糊）")],
    summary="渠道清算流水查询",
)
class ClearingQueryViewSet(_DataQueryViewSet):
    queryset = ClearingData.objects.select_related("channel", "biz_type", "file").all()
    serializer_class = ClearingSerializer


@extend_schema(parameters=DATE_PARAMS, summary="渠道结算数据查询")
class SettlementQueryViewSet(_DataQueryViewSet):
    queryset = SettlementData.objects.select_related("channel", "account", "file").all()
    serializer_class = SettlementSerializer
