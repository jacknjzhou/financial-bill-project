"""数据接入：InFile（上传记录）+ 三张源数据表（payment/clearing/settlement）。

不变式：
- 源数据行金额一律分（int）；tx_time 存 UTC，reconcile_date 为本地（UTC+8）日期。
- 三表 file FK 一律 PROTECT：已入库的数据不可因删除上传记录而消失（可追溯）。
- 后续 ReconcileResult/Dispute 对源数据的 FK 也必须 PROTECT（覆盖重传保护的基础）。
"""
from django.db import models

from apps.meta.models import BaseModel


def _data_upload_path(instance, filename: str) -> str:
    raise NotImplementedError  # 存储路径由 services 层拼接（/data/files/<task>/<date>/…）


class InFile(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待解析"
        PARSING = "parsing", "解析中"
        PARSED = "parsed", "已入库"
        FAILED = "failed", "解析失败"

    fetch_task = models.ForeignKey("rules.FetchTask", on_delete=models.PROTECT, related_name="files")
    file_name = models.CharField("文件名", max_length=255)
    storage_path = models.CharField("存储路径", max_length=512, blank=True, default="")
    size = models.BigIntegerField("字节数", default=0)
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, null=True, blank=True, related_name="uploads")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    total_rows = models.IntegerField("总行数", default=0)
    failed_rows = models.IntegerField("失败行数", default=0)
    error_msg = models.TextField("失败原因", blank=True, default="")
    created_date = models.DateField("上传日期", editable=False, db_index=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            # 同一获取任务同日同名防重（覆盖重传走显式 overwrite 通道）
            models.UniqueConstraint(
                fields=["fetch_task", "file_name", "created_date"], name="uniq_infile_task_name_date"
            )
        ]

    def __str__(self) -> str:
        return f"{self.fetch_task_id}/{self.file_name}({self.status})"


class PaymentData(BaseModel):
    """自有支付流水（A 方）。"""

    order_no = models.CharField("商户单号", max_length=64, db_index=True)
    pay_no = models.CharField("支付单号", max_length=64, blank=True, default="")
    channel = models.ForeignKey("meta.Channel", on_delete=models.PROTECT, null=True, blank=True, related_name="payment_rows")
    account = models.ForeignKey("meta.FundAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="payment_rows")
    biz_type = models.ForeignKey("meta.BizType", on_delete=models.PROTECT, null=True, blank=True, related_name="payment_rows")
    amount = models.BigIntegerField("金额（分）")
    status = models.CharField("状态", max_length=32)
    tx_time = models.DateTimeField("交易时间", null=True, blank=True)
    tx_date = models.DateField("交易日期（本地）", null=True, blank=True)
    reconcile_date = models.DateField("对账日期", db_index=True)
    file = models.ForeignKey(InFile, on_delete=models.PROTECT, null=True, blank=True, related_name="payment_rows")

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["reconcile_date", "order_no"])]


class ClearingData(BaseModel):
    """渠道清算/交易账单（B 方）。"""

    channel_order_no = models.CharField("渠道单号", max_length=64, db_index=True)
    order_no = models.CharField("商户单号", max_length=64, blank=True, default="")
    channel = models.ForeignKey("meta.Channel", on_delete=models.PROTECT, null=True, blank=True, related_name="clearing_rows")
    account = models.ForeignKey("meta.FundAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="clearing_rows")
    biz_type = models.ForeignKey("meta.BizType", on_delete=models.PROTECT, null=True, blank=True, related_name="clearing_rows")
    amount = models.BigIntegerField("金额（分）")
    status = models.CharField("状态", max_length=32)
    tx_time = models.DateTimeField("交易时间", null=True, blank=True)
    tx_date = models.DateField("交易日期（本地）", null=True, blank=True)
    reconcile_date = models.DateField("对账日期", db_index=True)
    file = models.ForeignKey(InFile, on_delete=models.PROTECT, null=True, blank=True, related_name="clearing_rows")

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["reconcile_date", "channel_order_no"])]


class SettlementData(BaseModel):
    """渠道结算文件（资金对账 B 方）。"""

    channel = models.ForeignKey("meta.Channel", on_delete=models.PROTECT, null=True, blank=True, related_name="settlement_rows")
    account = models.ForeignKey("meta.FundAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="settlement_rows")
    fee_item = models.CharField("费用项", max_length=64)
    amount = models.BigIntegerField("金额（分）")
    fee_amount = models.BigIntegerField("手续费（分）", null=True, blank=True)
    actual_amount = models.BigIntegerField("实收（分）", null=True, blank=True)
    settle_date = models.DateField("结算日期")
    reconcile_date = models.DateField("对账日期", db_index=True)
    file = models.ForeignKey(InFile, on_delete=models.PROTECT, null=True, blank=True, related_name="settlement_rows")

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["reconcile_date", "fee_item"])]
