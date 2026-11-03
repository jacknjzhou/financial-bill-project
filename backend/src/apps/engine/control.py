"""对账控制规则：can_run / create_run / claim_run（T10 引用）。"""
from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.engine.models import ReconcileRun
from apps.rules.models import ReconcileProject


def default_reconcile_date() -> date:
    """对账滞后一天（T+1 文件语义）。"""
    return timezone.localdate() - timedelta(days=1)


def can_run(
    project: ReconcileProject, date: date, rerun: bool = False, run: ReconcileRun | None = None
) -> tuple[bool, str]:
    """触发前检查：启用日期 → 已对账 → 连续性 → 执行中。

    run 可传入已锁定的既有 run（create_run 事务内复用，避免重复查询）。
    """
    if date < project.start_date:
        return False, f"对账日期早于项目启用日期 {project.start_date}"

    if run is None:
        run = ReconcileRun.objects.filter(project=project, reconcile_date=date).first()
    if run:
        if run.status == ReconcileRun.Status.RUNNING:
            return False, "该日期对账执行中，请稍候"
        if run.status == ReconcileRun.Status.SUCCESS and not rerun:
            return False, "该日期已对账成功，如需重跑请走重对"
        if run.status == ReconcileRun.Status.PENDING:
            return False, "该日期已有待执行的对账任务"

    if not rerun and date > project.start_date:
        prev = ReconcileRun.objects.filter(
            project=project, reconcile_date=date - timedelta(days=1)
        ).first()
        if prev is None or prev.status != ReconcileRun.Status.SUCCESS:
            return False, f"前日（{date - timedelta(days=1)}）未完成对账，请先补齐（对账必须连续）"

    return True, ""


def create_run(
    project: ReconcileProject, date: date, trigger: str, user=None
) -> tuple[ReconcileRun | None, bool, str]:
    """触发入口。检查与写入在同一事务内加行锁完成（防并发窗口）；新建竞态由
    唯一约束兜底 → 冲突返回 (None, False, reason)，视图归一为 409。"""
    from django.db import IntegrityError

    rerun = trigger == ReconcileRun.Trigger.RERUN
    try:
        with transaction.atomic():
            existing = (
                ReconcileRun.objects.select_for_update()
                .filter(project=project, reconcile_date=date)
                .first()
            )
            ok, reason = can_run(project, date, rerun=rerun, run=existing)
            if not ok:
                return None, False, reason

            if existing is not None:
                # 复用既有行（failed 重跑 / rerun）：重置生命周期字段
                run = existing
                run.status = ReconcileRun.Status.PENDING
                run.trigger = trigger
                run.triggered_by = user or run.triggered_by
                run.error = ""
                run.started_at = None
                run.finished_at = None
                run.a_total = run.b_total = run.match_cnt = 0
                run.one_a_cnt = run.one_b_cnt = run.wrong_cnt = 0
                run.save()
            else:
                try:
                    run = ReconcileRun.objects.create(
                        project=project,
                        reconcile_date=date,
                        status=ReconcileRun.Status.PENDING,
                        trigger=trigger,
                        triggered_by=user,
                    )
                except IntegrityError:
                    # 检查与创建之间的并发窗口撞唯一约束
                    return None, False, "并发触发冲突：该日期任务已存在"
    except IntegrityError:
        return None, False, "并发触发冲突：该日期任务已存在"
    return run, True, ""


def claim_run(run: ReconcileRun) -> bool:
    """任务侧抢占：select_for_update 下 PENDING→RUNNING；非 PENDING → False（no-op）。"""
    with transaction.atomic():
        locked = ReconcileRun.objects.select_for_update().filter(pk=run.pk).first()
        if locked is None or locked.status != ReconcileRun.Status.PENDING:
            return False
        locked.status = ReconcileRun.Status.RUNNING
        locked.started_at = timezone.now()
        locked.save(update_fields=["status", "started_at", "updated_at"])
        return True
