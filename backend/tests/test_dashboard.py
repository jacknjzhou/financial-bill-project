"""T13 工作台与告警：overview 聚合 + failed/dispute 告警（站内+邮件）。"""
from __future__ import annotations

from datetime import date

import pytest
from django.core import mail
from django.test import Client

from apps.accounts.models import User
from apps.meta.models import BizType, Channel
from apps.rules.models import ReconcileProject

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
def projects(db):
    channel = Channel.objects.create(code="wx", name="微信")
    BizType.objects.get_or_create(code="INCOME", defaults={"name": "收款", "group": "INCOME"})
    p1 = ReconcileProject.objects.create(
        name="P1", type="transaction", a_source="payment", b_source="clearing",
        match_key="order_no", start_date=date(2026, 10, 1),
    )
    p2 = ReconcileProject.objects.create(
        name="P2", type="transaction", a_source="payment", b_source="clearing",
        match_key="order_no", start_date=date(2026, 10, 1),
    )
    return {"p1": p1, "p2": p2}


def make_run(project, status, **counts):
    from apps.engine import control
    from apps.engine.models import ReconcileRun

    return ReconcileRun.objects.create(
        project=project, reconcile_date=control.default_reconcile_date(),
        status=status, trigger=ReconcileRun.Trigger.MANUAL, **counts,
    )


@pytest.fixture(autouse=True)
def locmem_mail(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.ALERT_EMAIL_TO = ["ops@example.com"]
    settings.EMAIL_FROM = "recon@local"
    mail.outbox.clear()


class TestDashboard:
    def test_overview(self, client, projects):
        from apps.engine.models import Alert

        make_run(projects["p1"], "success", a_total=10, b_total=9, match_cnt=8, one_a_cnt=1, wrong_cnt=1)
        failed = make_run(projects["p2"], "failed", error="B 方文件缺失")
        Alert.objects.create(project=projects["p1"], reconcile_date=date(2026, 10, 31), kind="dispute", message="差异 2 笔")
        Alert.objects.create(project=projects["p2"], reconcile_date=date(2026, 10, 31), kind="failed", message="失败")

        r = client.get("/api/v1/dashboard/overview")
        assert r.status_code == 200
        body = r.json()
        assert body["reconcile_date"]
        runs = {run["project"]: run for run in body["runs"]}
        assert runs[projects["p1"].id]["status"] == "success"
        assert runs[projects["p2"].id]["status"] == "failed"
        assert body["alerts_unread"] == 2

    def test_alert_on_failed(self, client, projects):
        from apps.engine.alerts import send_alert
        from apps.engine.models import Alert

        run = make_run(projects["p2"], "failed", error="B 方文件缺失")
        send_alert(run.project, run.reconcile_date, "failed", f"对账失败：{run.error}")
        assert len(mail.outbox) == 1
        assert "P2" in mail.outbox[0].subject
        assert Alert.objects.filter(kind="failed", read=False).count() == 1

    def test_alert_on_diff(self, projects):
        from apps.engine.tasks import _alert_on_summary

        make_run(projects["p1"], "success", a_total=10, b_total=9, match_cnt=8, one_a_cnt=1, wrong_cnt=1)
        run = _alert_on_summary(projects["p1"], date(2026, 10, 31), {"match_cnt": 8, "one_a_cnt": 1, "one_b_cnt": 0, "wrong_cnt": 1})
        assert run is True
        assert len(mail.outbox) == 1
        assert "差异" in mail.outbox[0].subject

    def test_no_alert_clean(self, projects):
        from apps.engine.tasks import _alert_on_summary

        _alert_on_summary(projects["p1"], date(2026, 10, 31), {"match_cnt": 10, "one_a_cnt": 0, "one_b_cnt": 0, "wrong_cnt": 0})
        assert len(mail.outbox) == 0
