"""演示数据 seed（幂等）：配置 + 10-31 全平数据入库 + 11-01 夹具文件。

11-01 场景（数字自洽）：A 60 行 / B 55 行 = 40 对平 + 10 单边A + 5 单边B + 10 错账。
夹具文件写入 data/demo/ 供 Playwright 冒烟通过 UI 上传（11-01 数据不入库）。
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path

from django.conf import settings as dj_settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.dataio.models import ClearingData, InFile, PaymentData
from apps.dataio.parsing import validate
from apps.engine.models import ReconcileRun
from apps.meta.models import BizType, Channel, DisputeType, FundAccount
from apps.rules.models import FetchTask, ParseRule, ReconcileProject

D31 = date(2026, 10, 31)
D01 = date(2026, 11, 1)
TX = "%Y-%m-%d %H:%M:%S"

PAYMENT_COLUMNS = ["商户单号", "支付单号", "渠道单号", "业务类型", "金额", "手续费", "状态", "交易时间"]
CLEARING_COLUMNS = ["商户单号", "渠道单号", "业务类型", "金额", "状态", "交易时间"]


class Command(BaseCommand):
    help = "初始化演示数据（幂等）：基础配置 + 10-31 全平 + 11-01 夹具文件"

    def handle(self, *args, **options):
        channel, biz, rules, tasks, project = self._ensure_config()
        self._seed_day31(channel, biz, rules, tasks, project)
        self._write_day01_fixtures(project)
        self._ensure_admin()
        self.stdout.write(self.style.SUCCESS("seed_demo 完成：admin/Admin@123；10-31 已对平；11-01 夹具在 data/demo/"))

    # ---------- 配置 ----------

    def _ensure_config(self):
        channel, _ = Channel.objects.get_or_create(code="wxpay", defaults={"name": "微信支付"})
        FundAccount.objects.get_or_create(
            channel=channel, name="微信主账户",
            defaults={"account_no": "mch-demo-001", "start_date": D31 - (D31 - date(2026, 10, 20)), "start_balance": 100_000_00},
        )
        for code, name, group in [("INCOME", "收款", "INCOME"), ("REFUND", "退款", "REFUND"), ("FEE", "手续费", "FEE"), ("RECHARGE", "充值", "INCOME")]:
            BizType.objects.get_or_create(code=code, defaults={"name": name, "group": group})
        for name, desc in [
            ("补单", "按渠道数据补录自有单据，处理后重对验证"),
            ("忽略-时间差", "跨日（如 23:59:59 支付次日清算）导致的单边：核实为时间差后忽略"),
            ("确认损失", "核实确认为损失：登记损失并留痕"),
            ("人工核实后忽略", "人工核实（截图/渠道后台对证）后忽略"),
        ]:
            DisputeType.objects.get_or_create(group="TRANSACTION", name=name, defaults={"description": desc})

        payment_rule, _ = ParseRule.objects.get_or_create(
            name="演示-自有支付模板",
            defaults={
                "target": "payment", "file_format": "csv", "encoding": "utf-8-sig",
                "header_row": 1,
                "column_map": {
                    "商户单号": "order_no", "支付单号": "pay_no", "渠道单号": "channel_order_no",
                    "业务类型": "biz_type", "金额": "amount", "手续费": "fee_amount",
                    "状态": "status", "交易时间": "tx_time",
                },
                "value_maps": {"status": {"成功": "SUCCESS", "失败": "FAIL"}},
                "amount_scale": 100,
            },
        )
        clearing_rule, _ = ParseRule.objects.get_or_create(
            name="演示-渠道清算模板",
            defaults={
                "target": "clearing", "file_format": "csv", "encoding": "utf-8-sig",
                "header_row": 1,
                "column_map": {
                    "商户单号": "order_no", "渠道单号": "channel_order_no",
                    "业务类型": "biz_type", "金额": "amount", "状态": "status", "交易时间": "tx_time",
                },
                "value_maps": {"status": {"成功": "SUCCESS", "失败": "FAIL"}},
                "amount_scale": 100,
            },
        )
        task_a, _ = FetchTask.objects.get_or_create(
            name="演示-平台支付上传", side="platform", channel=channel,
            defaults={"parse_rule": payment_rule},
        )
        task_b, _ = FetchTask.objects.get_or_create(
            name="演示-渠道清算上传", side="channel", channel=channel,
            defaults={"parse_rule": clearing_rule},
        )
        project, _ = ReconcileProject.objects.get_or_create(
            name="演示-微信交易对账",
            defaults={
                "type": "transaction", "a_source": "payment", "b_source": "clearing",
                "match_key": "order_no", "a_status_set": ["SUCCESS"], "b_status_set": ["SUCCESS"],
                "b_sum": True, "start_date": date(2026, 10, 20), "exec_time": "02:00:00",
            },
        )
        return channel, None, {"payment": payment_rule, "clearing": clearing_rule}, {"a": task_a, "b": task_b}, project

    # ---------- 10-31：全平 100/100 ----------

    def _seed_day31(self, channel, biz, rules, tasks, project):
        if ReconcileRun.objects.filter(project=project, reconcile_date=D31, status=ReconcileRun.Status.SUCCESS).exists():
            self.stdout.write("10-31 已 seed，跳过")
            return
        a_file = self._ingest_file(
            tasks["a"], rules["payment"], "demo-20261031-payment.csv", self._day31_csv(rules["payment"])
        )
        b_file = self._ingest_file(
            tasks["b"], rules["clearing"], "demo-20261031-clearing.csv", self._day31_csv(rules["clearing"])
        )
        ReconcileRun.objects.update_or_create(
            project=project, reconcile_date=D31,
            defaults={
                "status": ReconcileRun.Status.SUCCESS, "trigger": ReconcileRun.Trigger.AUTO,
                "a_total": 100, "b_total": 100, "match_cnt": 100,
                "started_at": timezone.now(), "finished_at": timezone.now(),
            },
        )

    def _day31_csv(self, rule) -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(PAYMENT_COLUMNS if rule.target == "payment" else CLEARING_COLUMNS)
        for i in range(100):
            tx = f"2026-10-31 {i // 60:02d}:{i % 60:02d}:00"
            if rule.target == "payment":
                w.writerow([f"D31A{i:04d}", f"pay{i:04d}", f"ch{i:04d}", "INCOME", "100.00", "0.60", "成功", tx])
            else:
                w.writerow([f"D31A{i:04d}", f"ch{i:04d}", "INCOME", "100.00", "成功", tx])
        return buf.getvalue().encode("utf-8")

    def _ingest_file(self, task, rule, filename: str, content: bytes) -> InFile:
        from django.db import transaction

        with transaction.atomic():
            in_file, created = InFile.objects.get_or_create(
                fetch_task=task, file_name=filename, created_date=D31,
                defaults={"size": len(content), "status": InFile.Status.PENDING, "created_date": D31},
            )
            if not created and in_file.status == InFile.Status.PARSED:
                return in_file

            result = validate.parse_file(content, rule)
            if not result.ok:
                raise RuntimeError(f"演示文件解析失败：{result.errors[:3]}")
            if rule.target == "payment":
                PaymentData.objects.filter(file=in_file).delete()
                PaymentData.objects.bulk_create([
                    PaymentData(
                        order_no=r["order_no"], pay_no=r.get("pay_no") or "",
                        channel=task.channel, account=task.account,
                        biz_type=BizType.objects.filter(code=r.get("biz_type")).first(),
                        amount=r["amount"], status=r["status"],
                        tx_time=r.get("tx_time"), tx_date=r.get("tx_date"),
                        reconcile_date=r["reconcile_date"], file=in_file,
                    )
                    for r in result.rows
                ], batch_size=1000)
            else:
                ClearingData.objects.filter(file=in_file).delete()
                ClearingData.objects.bulk_create([
                    ClearingData(
                        order_no=r.get("order_no") or "", channel_order_no=r["channel_order_no"],
                        channel=task.channel, account=task.account,
                        biz_type=BizType.objects.filter(code=r.get("biz_type")).first(),
                        amount=r["amount"], status=r["status"],
                        tx_time=r.get("tx_time"), tx_date=r.get("tx_date"),
                        reconcile_date=r["reconcile_date"], file=in_file,
                    )
                    for r in result.rows
                ], batch_size=1000)
            in_file.status = InFile.Status.PARSED
            in_file.total_rows = result.total
            in_file.save()
        return in_file

    # ---------- 11-01：夹具（60 A / 55 B：40 对平 10 单边A 5 单边B 10 错账） ----------

    def _write_day01_fixtures(self, project):
        demo_dir = Path(dj_settings.FILES_ROOT).parent / "demo"
        demo_dir.mkdir(parents=True, exist_ok=True)

        a_buf, b_buf = io.StringIO(), io.StringIO()
        wa, wb = csv.writer(a_buf), csv.writer(b_buf)
        wa.writerow(PAYMENT_COLUMNS)
        wb.writerow(CLEARING_COLUMNS)

        for i in range(40):  # 对平
            wa.writerow([f"D01{i:04d}", f"payd{i:04d}", f"chd{i:04d}", "INCOME", "200.00", "1.00", "成功", f"2026-11-01 {i // 60:02d}:{i % 60:02d}:00"])
            wb.writerow([f"D01{i:04d}", f"chd{i:04d}", "INCOME", "200.00", "成功", f"2026-11-01 {i // 60:02d}:{i % 60:02d}:00"])
        for i in range(10):  # 单边A（渠道无）
            n = 40 + i
            wa.writerow([f"D01{n:04d}", f"payd{n:04d}", "", "INCOME", "88.00", "0.40", "成功", f"2026-11-01 01:{n:02d}:00"])
        for i in range(5):  # 单边B（平台无）
            n = 50 + i
            wb.writerow([f"D01B{n:04d}", f"chdb{n:04d}", "INCOME", "66.00", "成功", f"2026-11-01 02:{n:02d}:00"])
        for i in range(10):  # 错账（金额差固定：A 150.00 / B 130.00，差 20.00 元）
            n = 100 + i
            wa.writerow([f"D01{n:04d}", f"payd{n:04d}", f"chd{n:04d}", "INCOME", "150.00", "0.75", "成功", f"2026-11-01 03:{i:02d}:00"])
            wb.writerow([f"D01{n:04d}", f"chd{n:04d}", "INCOME", "130.00", "成功", f"2026-11-01 03:{i:02d}:00"])

        (demo_dir / "demo-20261101-payment.csv").write_bytes(a_buf.getvalue().encode("utf-8"))
        (demo_dir / "demo-20261101-clearing.csv").write_bytes(b_buf.getvalue().encode("utf-8"))
        self.stdout.write(f"11-01 夹具：{demo_dir}")

    def _ensure_admin(self):
        from apps.accounts.models import User

        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"role": User.Role.ADMIN, "must_change_password": False},
        )
        admin.role = User.Role.ADMIN
        admin.must_change_password = False
        admin.is_active = True
        admin.set_password("Admin@123")
        admin.save()
