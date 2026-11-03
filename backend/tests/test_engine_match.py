"""T10 匹配算法：消费语义/状态集/diff_type/1vN 组溯源/幂等重对/跨日边界。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest
from django.test import Client
from django.utils import timezone as dj_tz

from apps.accounts.models import User
from apps.meta.models import BizType, Channel, FundAccount
from apps.rules.models import FetchTask, ParseRule, ReconcileProject

LOCAL = ZoneInfo("Asia/Shanghai")


def a_row(rid, order_no, amount_fen, status="SUCCESS", **extra):
    return {"id": rid, "amount": amount_fen, "status": status, "order_no": order_no, **extra}


def b_row(rid, order_no, amount_fen, status="SUCCESS", **extra):
    return {"id": rid, "amount": amount_fen, "status": status, "order_no": order_no, **extra}


def make_project(**kw) -> ReconcileProject:
    params = dict(
        name="P", type="transaction", a_source="payment", b_source="clearing",
        match_key="order_no", a_status_set=["SUCCESS"], b_status_set=["SUCCESS"],
        b_sum=False, start_date=date(2026, 10, 1),
    )
    params.update(kw)
    return ReconcileProject(**params)


class TestMatchPure:
    """纯函数层：内存 dict 行，不经 DB。"""

    def test_match(self):
        from apps.engine.matching import match

        p = make_project()
        out = match([a_row(1, "A1", 10000)], [b_row(2, "A1", 10000)], p)
        assert len(out) == 2  # A + B 各一条，同组
        a_res = next(r for r in out if r["a"])
        b_res = next(r for r in out if r["b"])
        assert a_res["status"] == "match" and b_res["status"] == "match"
        assert a_res["group_no"] == b_res["group_no"]

    def test_one_a(self):
        from apps.engine.matching import match

        out = match([a_row(1, "A1", 10000)], [], make_project())
        assert len(out) == 1 and out[0]["status"] == "one_a" and out[0]["a"]["id"] == 1

    def test_one_b(self):
        from apps.engine.matching import match

        out = match([], [b_row(2, "B1", 10000)], make_project())
        assert len(out) == 1 and out[0]["status"] == "one_b" and out[0]["b"]["id"] == 2

    def test_wrong_amount(self):
        from apps.engine.matching import match

        out = match([a_row(1, "A1", 8000)], [b_row(2, "A1", 10000)], make_project())
        a_res = next(r for r in out if r["a"])
        assert a_res["status"] == "wrong"
        assert a_res["diff_amount"] == 2000  # b - a 带符号
        assert a_res["diff_type"] == "amount"

    def test_wrong_status(self):
        from apps.engine.matching import match

        out = match([a_row(1, "A1", 10000)], [b_row(2, "A1", 10000, status="FAIL")], make_project())
        a_res = next(r for r in out if r["a"])
        assert a_res["status"] == "wrong"
        assert a_res["diff_type"] == "status"
        assert a_res["diff_amount"] == 0  # 仅状态不符：diff 记 0

    def test_wrong_both(self):
        from apps.engine.matching import match

        out = match([a_row(1, "A1", 8000)], [b_row(2, "A1", 10000, status="FAIL")], make_project())
        a_res = next(r for r in out if r["a"])
        assert a_res["diff_type"] == "both"

    def test_duplicate_a_keys(self):
        """A 方同 order_no 两行：逐行消费索引 → 一行 match 一行 one_a，不撞约束。"""
        from apps.engine.matching import match

        p = make_project()
        out = match(
            [a_row(1, "A1", 10000), a_row(2, "A1", 20000)],
            [b_row(3, "A1", 10000)],
            p,
        )
        statuses = sorted(r["status"] for r in out if r["a"])
        assert statuses == ["match", "one_a"]

    def test_multiple_b_no_sum(self):
        """b_sum=False 且 B 同键多行：A+组 → wrong 整组落库。"""
        from apps.engine.matching import match

        p = make_project(b_sum=False)
        out = match(
            [a_row(1, "A1", 10000)],
            [b_row(2, "A1", 6000), b_row(3, "A1", 5000)],
            p,
        )
        assert len(out) == 3  # A 一条 + B 组每行一条
        group_nos = {r["group_no"] for r in out}
        assert len(group_nos) == 1  # 同组
        a_res = next(r for r in out if r["a"])
        assert a_res["status"] == "wrong"
        assert a_res["diff_amount"] == 1000  # 组合计 11000 - A 10000

    def test_b_sum_1vN(self):
        from apps.engine.matching import match

        p = make_project(b_sum=True)
        out = match(
            [a_row(1, "A1", 10000)],
            [b_row(2, "A1", 5000), b_row(3, "A1", 5000)],
            p,
        )
        a_res = next(r for r in out if r["a"])
        assert a_res["status"] == "match"
        assert a_res["diff_amount"] == 0
        # B 组每行一条 result，同组
        b_res = [r for r in out if r["b"]]
        assert len(b_res) == 2 and all(r["status"] == "match" for r in b_res)
        assert len({r["group_no"] for r in out}) == 1

    def test_leftover_b_sum_grouped(self):
        """A 弹空后剩余 B：b_sum 开启按键聚合 one_b（同组）。"""
        from apps.engine.matching import match

        p = make_project(b_sum=True)
        out = match(
            [a_row(1, "A1", 10000)],
            [b_row(2, "B2", 5000), b_row(3, "B2", 5000), b_row(4, "B3", 700)],
            p,
        )
        one_bs = [r for r in out if r["status"] == "one_b"]
        assert len(one_bs) == 3
        b2 = [r for r in one_bs if r["b"]["order_no"] == "B2"]
        assert len({r["group_no"] for r in b2}) == 1  # B2 两行同组
        b3 = [r for r in one_bs if r["b"]["order_no"] == "B3"]
        assert len({r["group_no"] for r in b3}) == 1

    def test_filters(self):
        """a_filter biz_type eq 过滤在 collect 层（DB 集成段验证）。"""


# ---------- DB 集成段 ----------

pytestmark_db = pytest.mark.django_db(transaction=True)


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
    account = FundAccount.objects.create(
        channel=channel, name="主账户", start_date="2026-10-01", start_balance=0
    )
    BizType.objects.get_or_create(code="INCOME", defaults={"name": "收款", "group": "INCOME"})
    BizType.objects.get_or_create(code="REFUND", defaults={"name": "退款", "group": "REFUND"})
    rule = ParseRule.objects.create(
        name="r", target="payment", file_format="xlsx",
        column_map={"商户单号": "order_no", "支付单号": "pay_no", "渠道单号": "channel_order_no",
                    "业务类型": "biz_type", "金额": "amount", "状态": "status", "交易时间": "tx_time"},
        value_maps={"status": {"成功": "SUCCESS", "失败": "FAIL"}},
    )
    task = FetchTask.objects.create(name="t", side="platform", channel=channel, account=account, parse_rule=rule)
    project = ReconcileProject.objects.create(
        name="P", type="transaction", a_source="payment", b_source="clearing",
        match_key="order_no", a_status_set=["SUCCESS"], b_status_set=["SUCCESS"],
        b_sum=True, start_date=date(2026, 10, 1),
    )
    return {"channel": channel, "account": account, "task": task, "project": project}


def seed_payment(env, order_no, pay_no, amount, status, tx_local: datetime, reconcile_date, biz="INCOME", channel_order_no=None):
    from apps.dataio.models import PaymentData

    return PaymentData.objects.create(
        order_no=order_no, pay_no=pay_no,
        channel=env["channel"], account=env["account"],
        biz_type=BizType.objects.get(code=biz),
        amount=amount, status=status,
        tx_time=tx_local.astimezone(dt_timezone.utc) if tx_local.tzinfo is None else tx_local,
        tx_date=reconcile_date, reconcile_date=reconcile_date,
    )


def seed_clearing(env, order_no, channel_order_no, amount, status, tx_local: datetime, reconcile_date):
    from apps.dataio.models import ClearingData

    return ClearingData.objects.create(
        order_no=order_no, channel_order_no=channel_order_no,
        channel=env["channel"], account=env["account"],
        amount=amount, status=status,
        tx_time=tx_local if tx_local.tzinfo is not None else tx_local.replace(tzinfo=LOCAL),
        tx_date=reconcile_date, reconcile_date=reconcile_date,
    )


def run_for(env, d: str, rerun: bool = False):
    """匹配集成测试直接建 run 执行（绕开连续性控制——那是 T9 的测试对象）。"""
    from apps.engine.models import ReconcileRun
    from apps.engine.tasks import run_reconcile

    run = ReconcileRun.objects.filter(project=env["project"], reconcile_date=d).first()
    if run is None:
        run = ReconcileRun.objects.create(project=env["project"], reconcile_date=d, trigger=ReconcileRun.Trigger.MANUAL)
    else:
        run.status = ReconcileRun.Status.PENDING
        run.error = ""
        run.save(update_fields=["status", "error", "updated_at"])
    run_reconcile(run.id)
    run.refresh_from_db()
    return run


def _create_run(project, d, rerun):
    from apps.engine import control

    return control.create_run(project, d, "rerun" if rerun else "manual")


class TestMatchDB:
    @pytest.mark.django_db(transaction=True)
    def test_b_sum_group_traceability(self, client, env):
        """1vN match 落库：B 组每行都有 result 引用且共享 group_no；详情接口取回整组。"""
        from apps.dataio.models import ClearingData

        a = seed_payment(env, "A1", "p1", 10000, "SUCCESS", datetime(2026, 10, 31, 10, 0), date(2026, 10, 31))
        b1 = seed_clearing(env, "A1", "C1", 6000, "SUCCESS", datetime(2026, 10, 31, 10, 5), date(2026, 10, 31))
        b2 = seed_clearing(env, "A1", "C2", 4000, "SUCCESS", datetime(2026, 10, 31, 10, 6), date(2026, 10, 31))

        run = run_for(env, "2026-10-31")
        assert run.status == "success"
        assert (run.match_cnt, run.one_a_cnt, run.one_b_cnt, run.wrong_cnt) == (1, 0, 0, 0)
        assert run.a_total == 1 and run.b_total == 2

        from apps.engine.models import ReconcileResult

        a_res = ReconcileResult.objects.get(a=a)
        b_results = ReconcileResult.objects.filter(b__in=[b1, b2])
        assert b_results.count() == 2
        assert {r.group_no for r in b_results} == {a_res.group_no}

        # 详情接口按组取回 A 原文 + 全部 B 原文
        r = client.get(f"/api/v1/reconcile-results/{a_res.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["a_row"]["order_no"] == "A1"
        assert {b["channel_order_no"] for b in body["b_rows"]} == {"C1", "C2"}


    @pytest.mark.django_db(transaction=True)
    def test_reconcile_date_boundary(self, env):
        """审查重点 3：A 23:59:59、B 次日 00:00:01 → 各归各日，互不匹配。"""
        seed_payment(env, "A1", "p1", 10000, "SUCCESS", datetime(2026, 10, 31, 23, 59, 59), date(2026, 10, 31))
        seed_clearing(env, "A1", "C1", 10000, "SUCCESS", datetime(2026, 11, 1, 0, 0, 1), date(2026, 11, 1))

        run1 = run_for(env, "2026-10-31")
        assert (run1.one_a_cnt, run1.match_cnt) == (1, 0)
        run2 = run_for(env, "2026-11-01")
        assert (run2.one_b_cnt, run2.match_cnt) == (1, 0)

    @pytest.mark.django_db(transaction=True)
    def test_idempotent_rerun(self, env):
        seed_payment(env, "A1", "p1", 10000, "SUCCESS", datetime(2026, 10, 31, 10, 0), date(2026, 10, 31))
        seed_clearing(env, "A1", "C1", 10000, "SUCCESS", datetime(2026, 10, 31, 10, 0), date(2026, 10, 31))
        seed_payment(env, "A2", "p2", 5000, "SUCCESS", datetime(2026, 10, 31, 11, 0), date(2026, 10, 31))

        run1 = run_for(env, "2026-10-31")
        assert (run1.match_cnt, run1.one_a_cnt) == (1, 1)

        run2 = run_for(env, "2026-10-31", rerun=True)
        assert (run2.match_cnt, run2.one_a_cnt) == (1, 1)

        from apps.engine.models import ReconcileResult

        assert ReconcileResult.objects.filter(project=env["project"], reconcile_date="2026-10-31").count() == 3

    @pytest.mark.django_db(transaction=True)
    def test_write_and_counts(self, env):
        """重对先删旧再写同事务；run 计数=匹配产出；批量写 1000/批。"""
        from apps.engine import results
        from apps.engine.models import ReconcileRun, ReconcileResult

        # 构造 1200 条 B 无主 one_b 结果（batch 分片路径）
        rows = [{"status": "one_b", "a": None, "b": None, "match_key": f"K{i}",
                 "diff_amount": 0, "diff_type": "none", "biz_type": None} for i in range(1200)]
        run = ReconcileRun.objects.create(
            project=env["project"], reconcile_date=date(2026, 10, 31), trigger=ReconcileRun.Trigger.MANUAL
        )
        counts = results.write(run, rows)
        assert counts["one_b_cnt"] == 1200
        assert ReconcileResult.objects.filter(run=run).count() == 1200

        # 再写（重对）：旧结果删除，不重复
        results.write(run, rows[:100])
        assert ReconcileResult.objects.filter(run=run).count() == 100

    @pytest.mark.django_db(transaction=True)
    def test_empty_b(self, env):
        seed_payment(env, "A1", "p1", 10000, "SUCCESS", datetime(2026, 10, 31, 10, 0), date(2026, 10, 31))
        run = run_for(env, "2026-10-31")
        assert run.status == "success"
        assert (run.one_a_cnt, run.match_cnt) == (1, 0)

    @pytest.mark.django_db(transaction=True)
    def test_filters(self, env):
        """a_filter biz_type eq：只取 PAY 行进匹配。"""
        seed_payment(env, "A1", "p1", 10000, "SUCCESS", datetime(2026, 10, 31, 10, 0), date(2026, 10, 31), biz="INCOME")
        seed_payment(env, "A2", "p2", 20000, "SUCCESS", datetime(2026, 10, 31, 10, 0), date(2026, 10, 31), biz="REFUND")
        seed_clearing(env, "A1", "C1", 10000, "SUCCESS", datetime(2026, 10, 31, 10, 0), date(2026, 10, 31))

        env["project"].a_filter = [{"field": "biz_type", "op": "eq", "value": "INCOME"}]
        env["project"].save()

        run = run_for(env, "2026-10-31")
        assert run.a_total == 1  # REFUND 行被过滤
        assert run.match_cnt == 1
