"""T12 差错生命周期：物化（重对安全）+ 处理 + 留痕。"""
from __future__ import annotations

from datetime import date

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.meta.models import BizType, Channel, DisputeType, FundAccount
from apps.rules.models import FetchTask, ParseRule, ReconcileProject

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def admin(db):
    return User.objects.create_user("admin", password="Admin@123", role=User.Role.ADMIN, must_change_password=False)


@pytest.fixture
def client(admin):
    c = Client()
    c.force_login(admin)
    return c


@pytest.fixture
def env(db):
    channel = Channel.objects.create(code="wxpay", name="微信支付")
    FundAccount.objects.create(channel=channel, name="主账户", start_date="2026-10-01", start_balance=0)
    BizType.objects.get_or_create(code="INCOME", defaults={"name": "收款", "group": "INCOME"})
    DisputeType.objects.get_or_create(
        group="TRANSACTION", name="补单", defaults={"description": "按渠道数据补录自有单据"}
    )
    rule = ParseRule.objects.create(
        name="r", target="payment", file_format="xlsx",
        column_map={"商户单号": "order_no", "金额": "amount", "状态": "status", "交易时间": "tx_time"},
    )
    task = FetchTask.objects.create(name="t", side="platform", channel=channel, parse_rule=rule)
    project = ReconcileProject.objects.create(
        name="P", type="transaction", a_source="payment", b_source="clearing",
        match_key="order_no", a_status_set=["SUCCESS"], b_status_set=["SUCCESS"],
        start_date=date(2026, 10, 1),
    )
    return {"channel": channel, "task": task, "project": project}


def seed_run_results(env, *, one_a=2, wrong=1, match=5):
    """直接物化结果行：one_a×N、wrong×1、match×5（group_no 与匹配引擎同规则，保证重对幂等）。"""
    from apps.dataio.models import ClearingData, PaymentData
    from apps.engine.matching import _gno
    from apps.engine.models import ReconcileResult, ReconcileRun

    run = ReconcileRun.objects.create(
        project=env["project"], reconcile_date=date(2026, 10, 31), trigger=ReconcileRun.Trigger.MANUAL
    )
    biz = BizType.objects.get(code="INCOME")
    for i in range(match):
        a = PaymentData.objects.create(
            order_no=f"M{i}", pay_no=f"p{i}", channel=env["channel"], biz_type=biz,
            amount=10000, status="SUCCESS", reconcile_date=date(2026, 10, 31),
        )
        b = ClearingData.objects.create(
            order_no=f"M{i}", channel_order_no=f"C{i}", channel=env["channel"],
            amount=10000, status="SUCCESS", reconcile_date=date(2026, 10, 31),
        )
        ReconcileResult.objects.create(
            run=run, project=env["project"], reconcile_date=date(2026, 10, 31), status="match",
            a=a, b=b, match_key=f"M{i}", group_no=_gno(env["project"], f"M{i}", "A", a.pk),
        )
    for i in range(one_a):
        a = PaymentData.objects.create(
            order_no=f"OA{i}", pay_no=f"poa{i}", channel=env["channel"], biz_type=biz,
            amount=5000 + i, status="SUCCESS", reconcile_date=date(2026, 10, 31),
        )
        ReconcileResult.objects.create(
            run=run, project=env["project"], reconcile_date=date(2026, 10, 31), status="one_a",
            a=a, match_key=f"OA{i}", group_no=_gno(env["project"], f"OA{i}", "A", a.pk),
        )
    a = PaymentData.objects.create(
        order_no="W1", pay_no="pw1", channel=env["channel"], biz_type=biz,
        amount=8000, status="SUCCESS", reconcile_date=date(2026, 10, 31),
    )
    b = ClearingData.objects.create(
        order_no="W1", channel_order_no="CW1", channel=env["channel"],
        amount=10000, status="SUCCESS", reconcile_date=date(2026, 10, 31),
    )
    ReconcileResult.objects.create(
        run=run, project=env["project"], reconcile_date=date(2026, 10, 31), status="wrong",
        a=a, b=b, match_key="W1", diff_amount=2000, diff_type="amount",
        group_no=_gno(env["project"], "W1", "A", a.pk),
    )
    return run


class TestMaterialize:
    def test_materialize(self, client, env):
        from apps.disputes.models import Dispute, HandleLog
        from apps.disputes.services import materialize

        seed_run_results(env)
        created = materialize(env["project"], date(2026, 10, 31))
        assert created == 3  # one_a×2 + wrong×1（match 不物化）

        disputes = Dispute.objects.filter(project=env["project"], reconcile_date=date(2026, 10, 31))
        assert disputes.count() == 3
        assert disputes.filter(status="open").count() == 3
        wrong = disputes.get(type="wrong")
        assert wrong.amount == 8000  # A 代表行金额
        assert HandleLog.objects.filter(action="registered").count() == 3

        # 幂等：再物化不新增
        assert materialize(env["project"], date(2026, 10, 31)) == 0
        assert disputes.count() == 3

    def test_handle(self, client, env):
        from apps.disputes.models import Dispute, HandleLog
        from apps.disputes.services import materialize

        seed_run_results(env)
        materialize(env["project"], date(2026, 10, 31))
        dispute = Dispute.objects.get(type="wrong")
        dtype = DisputeType.objects.filter(group="TRANSACTION").first()
        assert dtype is not None

        # remark 必填
        r = client.post(f"/api/v1/disputes/{dispute.id}/handle",
                        data={"dispute_type_id": dtype.id, "remark": ""}, content_type="application/json")
        assert r.status_code == 400

        r = client.post(f"/api/v1/disputes/{dispute.id}/handle",
                        data={"dispute_type_id": dtype.id, "remark": "已补单并重对"}, content_type="application/json")
        assert r.status_code == 200, r.content
        dispute.refresh_from_db()
        assert dispute.status == "closed"
        assert dispute.handler_id is not None and dispute.handled_at is not None
        assert HandleLog.objects.filter(dispute=dispute).count() == 2  # registered + handled

    def test_handle_closed_409(self, client, env):
        from apps.disputes.models import Dispute
        from apps.disputes.services import materialize

        seed_run_results(env)
        materialize(env["project"], date(2026, 10, 31))
        dispute = Dispute.objects.get(type="wrong")
        dtype = DisputeType.objects.filter(group="TRANSACTION").first()
        assert client.post(f"/api/v1/disputes/{dispute.id}/handle",
                           data={"dispute_type_id": dtype.id, "remark": "ok"},
                           content_type="application/json").status_code == 200
        r = client.post(f"/api/v1/disputes/{dispute.id}/handle",
                        data={"dispute_type_id": dtype.id, "remark": "again"},
                        content_type="application/json")
        assert r.status_code == 409

    def test_rerun_safety(self, client, env):
        """重对安全：closed 保留 superseded、open 更新不新增、总数不变、无断引用。"""
        from apps.dataio.models import PaymentData
        from apps.disputes.models import Dispute, HandleLog
        from apps.disputes.services import materialize
        from apps.engine.models import ReconcileResult, ReconcileRun
        from apps.engine.tasks import run_reconcile

        seed_run_results(env)
        materialize(env["project"], date(2026, 10, 31))

        # 处理掉 wrong
        dispute = Dispute.objects.get(type="wrong")
        dtype = DisputeType.objects.filter(group="TRANSACTION").first()
        assert client.post(f"/api/v1/disputes/{dispute.id}/handle",
                           data={"dispute_type_id": dtype.id, "remark": "确认损失"},
                           content_type="application/json").status_code == 200

        # rerun：同日期重新执行 run（结果重建，键相同）
        run = ReconcileRun.objects.get(project=env["project"], reconcile_date=date(2026, 10, 31))
        run.status = ReconcileRun.Status.PENDING
        run.save(update_fields=["status"])
        run_reconcile(run.id)  # 成功后钩子自动 materialize

        disputes = Dispute.objects.filter(project=env["project"], reconcile_date=date(2026, 10, 31))
        assert disputes.count() == 3  # 总数不变
        closed = disputes.get(type="wrong")
        assert closed.status == "closed" and closed.superseded is True
        assert HandleLog.objects.filter(dispute=closed, action="closed_by_rerun").exists()
        # open 的 one_a 更新（reopened）而非新建
        assert disputes.filter(type="one_a", status="open").count() == 2
        assert HandleLog.objects.filter(dispute__type="one_a", action="reopened").count() == 2
        # 无断引用：所有 dispute 的 a/b 仍指向存在的行
        for d in disputes:
            if d.a_id:
                assert PaymentData.objects.filter(pk=d.a_id).exists()

    def test_list_api(self, client, env):
        from apps.disputes.services import materialize

        seed_run_results(env)
        materialize(env["project"], date(2026, 10, 31))
        r = client.get("/api/v1/disputes", {"project": env["project"].id})
        assert r.json()["total"] == 3
        r = client.get("/api/v1/disputes", {"status": "open"})
        assert r.json()["total"] == 3
        r = client.get("/api/v1/disputes", {"type": "one_a"})
        assert r.json()["total"] == 2

    def test_logs_api(self, client, env):
        from apps.disputes.models import Dispute
        from apps.disputes.services import materialize

        seed_run_results(env)
        materialize(env["project"], date(2026, 10, 31))
        dispute = Dispute.objects.get(type="wrong")
        r = client.get(f"/api/v1/disputes/{dispute.id}/logs")
        assert r.status_code == 200
        logs = r.json()["items"]
        assert len(logs) == 1 and logs[0]["action"] == "registered"
