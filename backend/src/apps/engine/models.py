"""对账引擎模型：Run 生命周期 + 结果存储 + Alert（告警模型在 T9 建立供 alerts.py 引用）。"""
import uuid

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


class ReconcileResult(BaseModel):
    """对账结果（独立存储：重对可整批重建，源数据永不改动）。

    group_no：同一匹配组共享——单行结果各自一个；1vN 汇总/多行错账时
    A 行与 B 组各行同 group_no（详情页与差错处理按组聚合取回整组）。
    """

    class Status(models.TextChoices):
        MATCH = "match", "对平"
        ONE_A = "one_a", "单边A"
        ONE_B = "one_b", "单边B"
        WRONG = "wrong", "错账"

    class DiffType(models.TextChoices):
        NONE = "none", "无"
        AMOUNT = "amount", "金额差"
        STATUS = "status", "状态不符"
        BOTH = "both", "金额+状态"

    run = models.ForeignKey(ReconcileRun, on_delete=models.PROTECT, related_name="results")
    project = models.ForeignKey("rules.ReconcileProject", on_delete=models.PROTECT, related_name="results")
    reconcile_date = models.DateField("对账日期", db_index=True)
    status = models.CharField("结果", max_length=8, choices=Status.choices)
    a = models.ForeignKey("dataio.PaymentData", on_delete=models.PROTECT, null=True, blank=True, related_name="results_as_a")
    b = models.ForeignKey("dataio.ClearingData", on_delete=models.PROTECT, null=True, blank=True, related_name="results_as_b")
    match_key = models.CharField("匹配键值", max_length=128, blank=True, default="")
    diff_amount = models.BigIntegerField("差异金额（分，b-a）", default=0)
    diff_type = models.CharField("差异类型", max_length=8, choices=DiffType.choices, default=DiffType.NONE)
    group_no = models.UUIDField("匹配组号", default=uuid.uuid4, db_index=True)
    biz_type = models.ForeignKey("meta.BizType", on_delete=models.PROTECT, null=True, blank=True, related_name="results")

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["project", "reconcile_date", "status"])]
        constraints = [
            # 同项目内每条源数据最多出现在一个结果中（重对先删旧再写，同事务）
            models.UniqueConstraint(
                fields=["project", "a"], condition=models.Q(a__isnull=False), name="uniq_result_project_a"
            ),
            models.UniqueConstraint(
                fields=["project", "b"], condition=models.Q(b__isnull=False), name="uniq_result_project_b"
            ),
        ]


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
