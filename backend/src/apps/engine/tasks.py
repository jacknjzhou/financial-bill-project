"""对账任务：run_reconcile（T9 骨架，T10 填实匹配）+ scan_due_runs（beat）。"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from apps.engine import control
from apps.engine.models import ReconcileRun

logger = logging.getLogger(__name__)


@shared_task
def run_reconcile(run_id: int) -> str:
    """执行一次对账：抢占 → 取数匹配 → 写库 → 计数落库。"""
    run = ReconcileRun.objects.select_related("project").get(pk=run_id)
    if not control.claim_run(run):
        return "skipped"  # 已被抢占/非 PENDING：幂等 no-op

    project = run.project
    try:
        from apps.engine.matching import collect_and_match  # T10 提供

        summary = collect_and_match(run)
    except Exception as e:  # noqa: BLE001 —— 任何异常 → run=failed + 告警
        logger.exception("run_reconcile failed: run#%s", run_id)
        run.status = ReconcileRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error = str(e)[:2000]
        run.save(update_fields=["status", "finished_at", "error", "updated_at"])
        from apps.engine.alerts import send_alert

        send_alert(project, run.reconcile_date, "failed", f"对账失败：{e}")
        return "failed"

    run.status = ReconcileRun.Status.SUCCESS
    run.finished_at = timezone.now()
    for field, value in summary.items():
        setattr(run, field, value)
    run.save(update_fields=["status", "finished_at", *summary.keys(), "updated_at"])

    _materialize_disputes(run)
    _alert_on_summary(project, run.reconcile_date, summary)
    return "success"


def _alert_on_summary(project, reconcile_date, summary: dict) -> bool:
    """run 成功但有差异 → dispute 告警（站内 + 邮件摘要）。全平不告警。"""
    diff_total = summary.get("one_a_cnt", 0) + summary.get("one_b_cnt", 0) + summary.get("wrong_cnt", 0)
    if diff_total <= 0:
        return False
    from apps.engine.alerts import send_alert

    send_alert(
        project,
        reconcile_date,
        "dispute",
        f"{project.name} {reconcile_date} 产生差异 {diff_total} 笔"
        f"（单边A {summary.get('one_a_cnt', 0)} / 单边B {summary.get('one_b_cnt', 0)} / 错账 {summary.get('wrong_cnt', 0)}），请及时处理",
    )
    return True


def _materialize_disputes(run) -> None:
    """T12 物化钩子（disputes 未启用时 no-op）。"""
    try:
        from apps.disputes.services import materialize
    except ImportError:
        return
    try:
        materialize(run.project, run.reconcile_date)
    except Exception:  # noqa: BLE001 —— 差异物化失败不回滚对账结果
        logger.exception("materialize disputes failed: run#%s", run.id)


@shared_task
def scan_due_runs() -> int:
    """beat 每 30 分钟：到期项目（enabled + exec_time 已过 + 昨日未对 + 连续性 OK）入队一次。

    幂等：ReconcileRun 唯一 (project, reconcile_date) 约束兜底，重复扫描不重复建。
    """
    from datetime import timedelta

    from apps.rules.models import ReconcileProject

    now = timezone.localtime()
    date = now.date() - timedelta(days=1)
    queued = 0
    for project in ReconcileProject.objects.filter(enabled=True):
        if project.exec_time and project.exec_time > now.time():
            continue
        run, ok, _reason = control.create_run(project, date, ReconcileRun.Trigger.AUTO)
        if ok:
            queued += 1
            transaction_on_commit_delay(run)
    return queued


def transaction_on_commit_delay(run) -> None:
    from django.db import transaction

    from .tasks import run_reconcile as run_reconcile_task

    transaction.on_commit(lambda: run_reconcile_task.delay(run.id))
