"""内置初始差错处理类型（规格：交易组 4 条；资金组留二期）。"""
from django.db import migrations


def forwards(apps, schema_editor):
    DisputeType = apps.get_model("meta", "DisputeType")
    if DisputeType.objects.exists():
        return
    DisputeType.objects.bulk_create(
        [
            DisputeType(group="TRANSACTION", name="补单", description="自有支付记录缺失而渠道已有：按渠道数据补录自有单据，处理后重对验证。"),
            DisputeType(group="TRANSACTION", name="忽略-时间差", description="跨日（如 23:59:59 支付次日清算）导致的单边：核实为时间差后忽略，次日自动对平。"),
            DisputeType(group="TRANSACTION", name="确认损失", description="核实确认为渠道侧已扣款但业务未达成等情形：登记损失并留痕。"),
            DisputeType(group="TRANSACTION", name="人工核实后忽略", description="无法自动化归因的差异：人工核实（截图/渠道后台对证）后忽略。"),
        ]
    )


def backwards(apps, schema_editor):
    apps.get_model("meta", "DisputeType").objects.filter(
        group="TRANSACTION", name__in=["补单", "忽略-时间差", "确认损失", "人工核实后忽略"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("meta", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
