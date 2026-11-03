"""T9 对账引擎控制规则：连续性/状态/并发抢占/beat 扫描。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.test import Client
from django.utils import timezone as dj_tz

from apps.accounts.models import User
from apps.rules.models import ReconcileProject

LOCAL = ZoneInfo("Asia/Shanghai")

pytestmark = pytest.mark.django_db(transaction=True)


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
def project(db):
    return ReconcileProject.objects.create(
        name="微信交易对账", type="transaction", a_source="payment", b_source="clearing",
        match_key="order_no", start_date=date(2026, 10, 1), exec_time=time(2, 0),
    )


def trigger(client, project, d: str, rerun: bool = False):
    body = {"rerun": rerun}
    if d:
        body["date"] = d
    return client.post(f"/api/v1/reconcile-projects/{project.id}/runs", data=body, content_type="application/json")


def make_success_run(project, d: str):
    from apps.engine.models import ReconcileRun

    return ReconcileRun.objects.create(
        project=project, reconcile_date=d, status=ReconcileRun.Status.SUCCESS,
        trigger=ReconcileRun.Trigger.AUTO, a_total=1, b_total=1, match_cnt=1,
    )


class TestControlRules:
    def test_before_start(self, client, project):
        r = trigger(client, project, "2026-09-30")
        assert r.status_code == 409
        assert "启用日期" in r.json()["error"]["message"]

    def test_continuity_block(self, client, project):
        r = trigger(client, project, "2026-10-02")
        assert r.status_code == 409
        assert "前日" in r.json()["error"]["message"]
        # 10-01 success 后 → 202
        make_success_run(project, "2026-10-01")
        r = trigger(client, project, "2026-10-02")
        assert r.status_code == 202, r.content

    def test_rerun_skips_continuity(self, client, project):
        r = trigger(client, project, "2026-10-02", rerun=True)
        assert r.status_code == 202, r.content

    def test_success_rerun_required(self, client, project):
        make_success_run(project, "2026-10-01")
        r = trigger(client, project, "2026-10-01")
        assert r.status_code == 409
        assert "重对" in r.json()["error"]["message"]
        r = trigger(client, project, "2026-10-01", rerun=True)
        assert r.status_code == 202

    def test_concurrent_trigger(self, client, project):
        """审查重点 5：两线程同 (P,D) → 恰一个 202，一个 409，run 仅 1 条。"""
        import threading

        results: list[int] = []

        def do():
            c = Client()
            c.force_login(User.objects.get(username="admin"))
            r = trigger(c, project, "2026-10-01")
            results.append(r.status_code)

        t1, t2 = threading.Thread(target=do), threading.Thread(target=do)
        t1.start(); t2.start(); t1.join(); t2.join()

        assert sorted(results) == [202, 409]
        from apps.engine.models import ReconcileRun

        assert ReconcileRun.objects.filter(project=project, reconcile_date="2026-10-01").count() == 1

    def test_beat_scan(self, client, project, settings):
        from apps.engine.tasks import scan_due_runs

        now = dj_tz.localtime()
        yesterday = now.date() - timedelta(days=1)
        # 项目启用日期 = 昨天（免连续性前置），exec_time 已过
        project.start_date = yesterday
        project.exec_time = time(0, 0)
        project.save()

        scan_due_runs()
        from apps.engine.models import ReconcileRun

        runs = ReconcileRun.objects.filter(project=project, reconcile_date=yesterday)
        assert runs.count() == 1
        assert runs.first().trigger == ReconcileRun.Trigger.AUTO

        # 再扫一次：不重复入队
        scan_due_runs()
        assert ReconcileRun.objects.filter(project=project, reconcile_date=yesterday).count() == 1

        # 启用日期更早（有连续性前置）但昨日无 success → 不入队
        ReconcileRun.objects.all().delete()
        project.start_date = yesterday - timedelta(days=5)
        project.save()
        scan_due_runs()
        assert ReconcileRun.objects.filter(project=project).count() == 0
