"""内置默认解析模板（规格：界面可改；列映射按常见渠道文件预填）。"""
from django.db import migrations


TEMPLATES = [
    {
        "name": "自有支付导出",
        "target": "payment",
        "file_format": "csv",
        "encoding": "utf-8-sig",
        "delimiter": ",",
        "header_row": 1,
        "column_map": {
            "订单号": "order_no",
            "支付单号": "pay_no",
            "渠道": "channel",
            "账户": "account",
            "业务类型": "biz_type",
            "金额(元)": "amount",
            "状态": "status",
            "时间": "tx_time",
        },
        "value_maps": {"status": {"成功": "SUCCESS", "失败": "FAIL", "关闭": "CLOSED"}},
        "amount_scale": 100,
        "time_format": "%Y-%m-%d %H:%M:%S",
    },
    {
        "name": "微信支付清算文件",
        "target": "clearing",
        "file_format": "csv",
        "encoding": "utf-8-sig",
        "delimiter": ",",
        "header_row": 1,
        "column_map": {
            "商户单号": "order_no",
            "微信支付单号": "channel_order_no",
            "业务类型": "biz_type",
            "金额(元)": "amount",
            "退款金额(元)": "fee_amount",
            "交易状态": "status",
            "交易时间": "tx_time",
        },
        "value_maps": {"status": {"SUCCESS": "SUCCESS", "SUCCESS ": "SUCCESS", "退款成功": "SUCCESS"}},
        "amount_scale": 100,
        "time_format": "%Y-%m-%d %H:%M:%S",
    },
    {
        "name": "支付宝结算文件",
        "target": "settlement",
        "file_format": "csv",
        "encoding": "utf-8-sig",
        "delimiter": ",",
        "header_row": 1,
        "column_map": {
            "商户订单号": "order_no",
            "支付宝交易号": "channel_order_no",
            "业务类型": "fee_item",
            "收入金额(元)": "amount",
            "费用(元)": "fee_amount",
            "实收金额(元)": "actual_amount",
            "结算日期": "settle_date",
        },
        "value_maps": {},
        "amount_scale": 100,
        "time_format": "%Y-%m-%d",
    },
]


def forwards(apps, schema_editor):
    ParseRule = apps.get_model("rules", "ParseRule")
    if ParseRule.objects.exists():
        return
    ParseRule.objects.bulk_create([ParseRule(**t) for t in TEMPLATES])


def backwards(apps, schema_editor):
    apps.get_model("rules", "ParseRule").objects.filter(
        name__in=[t["name"] for t in TEMPLATES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("rules", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
