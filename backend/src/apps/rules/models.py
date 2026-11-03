"""解析规则、获取任务、对账项目（配置域核心：可配置性是对账系统的根基）。"""
from django.db import models

from apps.meta.models import BaseModel

# 标准字段集合（规格钉死；解析目标与匹配键均从此取值）
STANDARD_FIELDS = [
    "order_no", "pay_no", "channel_order_no", "channel", "account",
    "biz_type", "fee_item", "amount", "fee_amount", "actual_amount",
    "status", "tx_time", "settle_date",
]


class ParseRule(BaseModel):
    class Target(models.TextChoices):
        PAYMENT = "payment", "自有支付"
        CLEARING = "clearing", "渠道清算"
        SETTLEMENT = "settlement", "渠道结算"

    class FileFormat(models.TextChoices):
        XLSX = "xlsx", "Excel"
        CSV = "csv", "CSV"
        TXT = "txt", "TXT"

    name = models.CharField("名称", max_length=64, unique=True)
    target = models.CharField("目标表", max_length=16, choices=Target.choices)
    file_format = models.CharField("文件格式", max_length=8, choices=FileFormat.choices)
    encoding = models.CharField(
        "文件编码", max_length=16, default="utf-8-sig",
        help_text="csv/txt 用；utf-8-sig 解码失败自动回退 gb18030",
    )
    delimiter = models.CharField("分隔符（txt）", max_length=4, default=",")
    header_row = models.IntegerField("表头行号", default=1)
    column_map = models.JSONField(
        "列映射", help_text='文件列名 → 标准字段（如 {"商户单号":"order_no"}；键为空串的项忽略）'
    )
    value_maps = models.JSONField(
        "值映射", default=dict, blank=True,
        help_text='{"字段":{"文件值":"标准值"}}，如 {"status":{"成功":"SUCCESS"}}',
    )
    amount_scale = models.IntegerField("金额进制乘数", default=100, help_text="元→分 ×100")
    time_format = models.CharField("时间格式", max_length=64, default="%Y-%m-%d %H:%M:%S")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class FetchTask(BaseModel):
    """获取任务：一期固定 manual_upload（上传槽位），三期扩展 api/sftp/sql。"""

    class Side(models.TextChoices):
        PLATFORM = "platform", "自有平台"
        CHANNEL = "channel", "渠道"

    name = models.CharField("名称", max_length=64)
    side = models.CharField("侧", max_length=16, choices=Side.choices)
    channel = models.ForeignKey("meta.Channel", on_delete=models.PROTECT, null=True, blank=True, related_name="fetch_tasks")
    account = models.ForeignKey("meta.FundAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="fetch_tasks")
    parse_rule = models.ForeignKey(ParseRule, on_delete=models.PROTECT, related_name="fetch_tasks")
    mode = models.CharField("获取方式", max_length=16, default="manual_upload")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class ReconcileProject(BaseModel):
    class Type(models.TextChoices):
        TRANSACTION = "transaction", "交易对账"
        FUND = "fund", "资金对账"
        BALANCE = "balance", "余额调节"

    name = models.CharField("名称", max_length=64, unique=True)
    type = models.CharField("类型", max_length=16, choices=Type.choices, default=Type.TRANSACTION)
    a_source = models.CharField("A 方数据源", max_length=16)  # payment/clearing/settlement
    a_filter = models.JSONField("A 方筛选条件", default=list, blank=True)
    b_source = models.CharField("B 方数据源", max_length=16)
    b_filter = models.JSONField("B 方筛选条件", default=list, blank=True)
    match_key = models.CharField("匹配键字段", max_length=32, default="order_no")
    a_status_set = models.JSONField("A 方期望状态集", default=list)
    b_status_set = models.JSONField("B 方期望状态集", default=list)
    b_sum = models.BooleanField("B 方同键汇总", default=False)
    start_date = models.DateField("启用日期")
    last_date = models.DateField("最后对账日期", null=True, blank=True)
    exec_time = models.TimeField("执行时间", default="02:00:00")
    alert_users = models.ManyToManyField("accounts.User", blank=True, related_name="alert_projects")
    enabled = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name
