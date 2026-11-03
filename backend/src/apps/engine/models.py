"""对账引擎模型：Run 生命周期 + Alert（告警模型在 T9 建立供 alerts.py 引用）。"""
from django.db import models

from apps.meta.models import BaseModel


class ReconcileRun(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待执行"
        RUNNING = "running", "执行中"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失败"

    class Trigger(models.TextChoices):
        AUTO = "auto", "定时"
        MANUAL = "manual", "手工"
        RERUN = "rerun", "重对"

    project = models.ForeignKey("rules.ReconcileProject", on_delete=models.PROTECT, related_name="runs")
    reconcile_date = models.DateField("对账日期", db_index=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    a_total = models.IntegerField("A 方笔数", default=0)
    b_total = models.IntegerField("B 方笔数", default=0)
    match_cnt = models.IntegerField("对平", default=0)
    one_a_cnt = models.IntegerField("单边A", default=0)
    one_b_cnt = models.IntegerField("单边B", default=0)
    wrong_cnt = models.IntegerField("错账", default=0)
    trigger = models.CharField("触发方式", max_length=16, choices=Trigger.choices, default=Trigger.MANUAL)
    triggered_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, null=True, blank=True, related_name="triggered_runs")
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    error = models.TextField("失败原因", blank=True, default="")

    class Meta:
        ordering = ["-id"]
        constraints = [
            # 同一项目同一对账日期只允许一个 run（重对复用该行重置）
            models.UniqueConstraint(fields=["project", "reconcile_date"], name="uniq_run_project_date")
        ]

    def __str__(self) -> str:
        return f"{self.project_id}@{self.reconcile_date}({self.status})"


class Alert(BaseModel):
    class Kind(models.TextChoices):
        FAILED = "failed", "对账失败"
        DISPUTE = "dispute", "新差异"

    project = models.ForeignKey("rules.ReconcileProject", on_delete=models.CASCADE, related_name="alerts")
    reconcile_date = models.DateField("对账日期")
    kind = models.CharField("类型", max_length=16, choices=Kind.choices)
    message = models.TextField("内容")
    read = models.BooleanField("已读", default=False)

    class Meta:
        ordering = ["-id"]
