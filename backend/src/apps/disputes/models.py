"""差错处理模型：Dispute（幂等键 project+date+group_no）+ HandleLog（留痕）。"""
from django.db import models

from apps.meta.models import BaseModel


class Dispute(BaseModel):
    class Type(models.TextChoices):
        ONE_A = "one_a", "单边A"
        ONE_B = "one_b", "单边B"
        WRONG = "wrong", "错账"

    class Status(models.TextChoices):
        OPEN = "open", "待处理"
        PROCESSING = "processing", "处理中"
        CLOSED = "closed", "已处理"

    project = models.ForeignKey("rules.ReconcileProject", on_delete=models.PROTECT, related_name="disputes")
    reconcile_date = models.DateField("对账日期", db_index=True)
    type = models.CharField("差异类型", max_length=8, choices=Type.choices)
    a = models.ForeignKey("dataio.PaymentData", on_delete=models.PROTECT, null=True, blank=True, related_name="disputes")
    b = models.ForeignKey("dataio.ClearingData", on_delete=models.PROTECT, null=True, blank=True, related_name="disputes")
    group_no = models.UUIDField("结果组号", null=True, blank=True, db_index=True)
    amount = models.BigIntegerField("金额（分）", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.OPEN)
    dispute_type = models.ForeignKey("meta.DisputeType", on_delete=models.PROTECT, null=True, blank=True, related_name="disputes")
    handler = models.ForeignKey("accounts.User", on_delete=models.PROTECT, null=True, blank=True, related_name="handled_disputes")
    handled_at = models.DateTimeField("处理时间", null=True, blank=True)
    remark = models.TextField("处理备注", blank=True, default="")
    superseded = models.BooleanField("已被重对覆盖", default=False)

    class Meta:
        ordering = ["-id"]
        constraints = [
            # 幂等键：同项目同日同组只一条 dispute（覆盖 1vN/多行错账聚合）
            models.UniqueConstraint(
                fields=["project", "reconcile_date", "group_no"],
                condition=models.Q(group_no__isnull=False),
                name="uniq_dispute_project_date_group",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.project_id}@{self.reconcile_date} {self.type} {self.status}"


class HandleLog(BaseModel):
    """处理留痕：全部状态迁移与动作均落一条 log（时间线倒序展示）。"""

    class Action(models.TextChoices):
        REGISTERED = "registered", "登记"
        PROCESSING = "processing", "转处理中"
        HANDLED = "handled", "处理完成"
        REOPENED = "reopened", "重对刷新"
        CLOSED_BY_RERUN = "closed_by_rerun", "重对后保留"

    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField("动作", max_length=16, choices=Action.choices)
    operator = models.ForeignKey("accounts.User", on_delete=models.PROTECT, null=True, blank=True, related_name="handle_logs")
    from_status = models.CharField("原状态", max_length=16, blank=True, default="")
    to_status = models.CharField("新状态", max_length=16, blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        ordering = ["-id"]
