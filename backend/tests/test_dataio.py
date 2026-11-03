"""T8 文件上传与数据入库：防重/回滚/覆盖保护/并发/限额/查询/下载。"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.meta.models import BizType, Channel, FundAccount
from apps.rules.models import FetchTask, ParseRule

FIXTURES = Path(__file__).parent / "fixtures" / "files"

# on_commit + eager：真实提交后立即执行任务（transaction=True 才能触发）
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def eager_celery(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def files_root(settings):
    """项目内临时存储目录（沙箱下 pytest tmp_path 不可用）。"""
    import shutil
    import uuid as _uuid

    root = Path(__file__).parent.parent / ".tmp-test-files" / _uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    settings.FILES_ROOT = root
    yield root
    shutil.rmtree(root.parent, ignore_errors=True)


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        "admin", password="Admin@123", role=User.Role.ADMIN, must_change_password=False
    )


@pytest.fixture
def client(admin):
    c = Client()
    c.force_login(admin)
    return c


@pytest.fixture
def setup(db):
    channel = Channel.objects.create(code="wxpay", name="微信支付")
    account = FundAccount.objects.create(
        channel=channel, name="微信主账户", account_no="mch-1",
        start_date="2026-10-01", start_balance=100_000_00,
    )
    biz = BizType.objects.create(code="INCOME", name="收款", group="INCOME")
    rule = ParseRule.objects.create(
        name="平台支付模板", target="payment", file_format="xlsx", header_row=1,
        column_map={
            "商户单号": "order_no", "支付单号": "pay_no", "渠道单号": "channel_order_no",
            "业务类型": "biz_type", "金额": "amount", "手续费": "fee_amount",
            "状态": "status", "交易时间": "tx_time",
        },
        value_maps={"status": {"成功": "SUCCESS", "失败": "FAIL"}},
        amount_scale=100, time_format="%Y-%m-%d %H:%M:%S",
    )
    task = FetchTask.objects.create(
        name="平台支付上传", side="platform", channel=channel, account=account,
        parse_rule=rule, mode="manual_upload"
    )
    return {"channel": channel, "account": account, "biz": biz, "rule": rule, "task": task}


def xlsx_bytes(rows: list[list] | None = None) -> bytes:
    from openpyxl import Workbook

    if rows is None:
        rows = [
            ["1001", "pay1", "ch1", "INCOME", "100.50", "0.30", "成功", "2026-10-31 10:00:00"],
            ["1002", "pay2", "ch2", "INCOME", "200.00", "0.60", "成功", "2026-10-31 11:00:00"],
            ["1003", "pay3", "ch3", "REFUND", "50.25", "0.15", "失败", "2026-10-31 12:00:00"],
        ]
    wb = Workbook()
    ws = wb.active
    ws.append(["商户单号", "支付单号", "渠道单号", "业务类型", "金额", "手续费", "状态", "交易时间"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def upload(client, task_id: int, filename: str, content: bytes, overwrite: bool = False):
    from django.core.files.uploadedfile import SimpleUploadedFile

    q = "?overwrite=true" if overwrite else ""
    return client.post(
        f"/api/v1/files{q}",
        data={"fetch_task": task_id, "file": SimpleUploadedFile(filename, content)},
    )


class TestUploadAndParse:
    def test_upload_and_parse(self, client, setup, files_root):
        # 存储目录由 files_root fixture 配置
        r = upload(client, setup["task"].id, "good.xlsx", xlsx_bytes())
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["status"] == "parsed"  # eager：POST 返回前任务已执行
        assert body["total_rows"] == 3

        from apps.dataio.models import PaymentData

        rows = PaymentData.objects.order_by("order_no")
        assert rows.count() == 3
        first = rows.first()
        assert first.amount == 10050  # 分
        assert first.status == "SUCCESS"
        assert str(first.reconcile_date) == "2026-10-31"
        assert first.channel_id == setup["channel"].id
        assert first.file_id is not None

    def test_bad_file_rollback(self, client, setup, files_root):
        # 存储目录由 files_root fixture 配置
        bad = xlsx_bytes(rows=[
            ["2001", "pay2001", "ch2001", "INCOME", "10.00", "0.30", "成功", "2026-10-31 10:00:00"],
            ["2002", "pay2002", "ch2002", "INCOME", "abc", "0.60", "成功", "2026-10-31 11:00:00"],
        ])
        r = upload(client, setup["task"].id, "bad.xlsx", bad)
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "failed"
        assert "行 2" in body["error_msg"]
        assert body["total_rows"] == 2

        from apps.dataio.models import PaymentData

        assert PaymentData.objects.count() == 0  # 整批回滚：无脏数据

    def test_duplicate_upload_409(self, client, setup, files_root):
        # 存储目录由 files_root fixture 配置
        assert upload(client, setup["task"].id, "good.xlsx", xlsx_bytes()).status_code == 201
        r = upload(client, setup["task"].id, "good.xlsx", xlsx_bytes())
        assert r.status_code == 409

    def test_overwrite_upload(self, client, setup, files_root):
        # 存储目录由 files_root fixture 配置
        assert upload(client, setup["task"].id, "good.xlsx", xlsx_bytes()).status_code == 201
        new_rows = [["3001", "pay3001", "ch3001", "INCOME", "88.00", "0.20", "成功", "2026-10-31 10:00:00"]]
        r = upload(client, setup["task"].id, "good.xlsx", xlsx_bytes(rows=new_rows), overwrite=True)
        assert r.status_code == 201, r.content

        from apps.dataio.models import InFile, PaymentData

        assert PaymentData.objects.count() == 1
        assert PaymentData.objects.first().order_no == "3001"
        # 旧 InFile 被替换（同名同任务仅一条有效）
        assert InFile.objects.count() == 1

    def test_overwrite_after_reconcile_409(self, client, setup, files_root):
        # 存储目录由 files_root fixture 配置
        from django.apps import apps as dj_apps

        from apps.dataio.models import PaymentData

        if not dj_apps.is_installed("apps.engine"):
            pytest.skip("T10 engine 未实现，409 保护在 T10 后生效（见 _file_is_reconciled）")

        try:
            from apps.engine.models import ReconcileResult
        except ImportError:
            pytest.skip("ReconcileResult 模型在 T10 建立")
        from apps.rules.models import ReconcileProject

        assert upload(client, setup["task"].id, "good.xlsx", xlsx_bytes()).status_code == 201
        project = ReconcileProject.objects.create(
            name="P1", type="transaction", a_source="payment", b_source="clearing",
            match_key="order_no", start_date="2026-10-01",
        )
        ReconcileResult.objects.create(
            project=project, reconcile_date="2026-10-31", status="match",
            a=PaymentData.objects.first(), match_key="1001",
        )

        r = upload(client, setup["task"].id, "good.xlsx", xlsx_bytes(), overwrite=True)
        assert r.status_code == 409
        # 旧数据完好
        assert PaymentData.objects.count() == 3

    def test_concurrent_upload_same_task(self, client, setup, files_root):
        """审查重点 5：同文件并发 POST → 一个 201 一个 409。"""
        import threading

        # 存储目录由 files_root fixture 配置
        results: list[int] = []

        def do_upload():
            c = Client()
            c.force_login(User.objects.get(username="admin"))
            r = upload(c, setup["task"].id, "good.xlsx", xlsx_bytes())
            results.append(r.status_code)

        t1, t2 = threading.Thread(target=do_upload), threading.Thread(target=do_upload)
        t1.start(); t2.start(); t1.join(); t2.join()

        assert sorted(results) == [201, 409]

        from apps.dataio.models import InFile, PaymentData

        assert InFile.objects.count() == 1
        assert PaymentData.objects.count() == 3  # 只解析一次

    def test_size_limit(self, client, setup, files_root):
        # 存储目录由 files_root fixture 配置
        big = b"\x00" * (50 * 1024 * 1024 + 1)
        r = upload(client, setup["task"].id, "big.xlsx", big)
        assert r.status_code == 400

    def test_extension_mismatch(self, client, setup, files_root):
        # 存储目录由 files_root fixture 配置
        r = upload(client, setup["task"].id, "good.csv", b"not,xlsx\n")
        assert r.status_code == 400


class TestQueryAndDownload:
    @pytest.fixture(autouse=True)
    def _uploaded(self, client, setup, files_root):
        # 存储目录由 files_root fixture 配置
        assert upload(client, setup["task"].id, "good.xlsx", xlsx_bytes()).status_code == 201

    def test_query_api(self, client):
        r = client.get("/api/v1/payments", {"reconcile_date": "2026-10-31"})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        r = client.get("/api/v1/payments", {"order_no": "1001"})
        assert r.json()["total"] == 1
        r = client.get("/api/v1/payments", {"status": "SUCCESS"})
        assert r.json()["total"] == 2
        r = client.get("/api/v1/clearings")
        assert r.status_code == 200 and r.json()["total"] == 0
        r = client.get("/api/v1/settlements")
        assert r.status_code == 200

    def test_files_list_and_download(self, client):
        r = client.get("/api/v1/files")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1 and items[0]["status"] == "parsed"
        fid = items[0]["id"]
        r = client.get(f"/api/v1/files/{fid}/download")
        assert r.status_code == 200
        assert r.get("Content-Disposition") is not None
