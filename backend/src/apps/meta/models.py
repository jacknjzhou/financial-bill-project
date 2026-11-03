"""基础字典：支付渠道、资金账户、业务类型、差错处理类型（规格 §6 配置域）。"""
from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True


class Channel(BaseModel):
    code = models.CharField("渠道编码", max_length=32, unique=True)
    name = models.CharField("渠道名称", max_length=64)
    enabled = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class FundAccount(BaseModel):
    """资金账户（规格：启用日期 + 启用余额至关重要，二期余额调节依赖，必须 100% 准确）。"""

    channel = models.ForeignKey(Channel, on_delete=models.PROTECT, related_name="accounts")
    name = models.CharField("账户名称", max_length=64)
    account_no = models.CharField("商户号/账号", max_length=64, blank=True, default="")
    start_date = models.DateField("启用日期")
    start_balance = models.BigIntegerField("启用余额（分）", help_text="单位：分")
    enabled = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class BizType(BaseModel):
    class Group(models.TextChoices):
        INCOME = "INCOME", "收款"
        REFUND = "REFUND", "退款"
        FEE = "FEE", "费用"

    code = models.CharField("业务类型编码", max_length=32, unique=True)
    name = models.CharField("名称", max_length=64)
    group = models.CharField("分组", max_length=16, choices=Group.choices)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class DisputeType(BaseModel):
    """差错处理类型（可配置 SOP）：执行处理时选类型 = 选 SOP。"""

    class Group(models.TextChoices):
        TRANSACTION = "TRANSACTION", "交易"
        FUND = "FUND", "资金"

    group = models.CharField("分组", max_length=16, choices=Group.choices)
    name = models.CharField("名称", max_length=64)
    description = models.TextField("SOP 说明", blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name
