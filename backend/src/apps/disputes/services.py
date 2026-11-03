"""差错物化：非 match 结果按 group_no 聚合 → 差异登记（重对安全）。"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.disputes.models import Dispute, HandleLog
from apps.engine.models import ReconcileResult


def materialize(project, reconcile_date) -> int:
    """把 (project, date) 的非 match 结果聚合成组并落 Dispute。

    - 每组取"代表行"（优先 A 侧行）决定 type/amount/a/b；
    - 已 closed → 保留 + superseded=True + log closed_by_rerun，不新建；
    - open/processing → 更新字段 + log reopened；
    - 无 → create + log registered。
    返回新建条数。单事务，幂等可重复调用。
    """
    results = list(
        ReconcileResult.objects.filter(
            project=project, reconcile_date=reconcile_date
        ).exclude(status="match").select_related("a", "b").order_by("id")
    )
    if not results:
        return 0

    groups: dict = {}
    for r in results:
        groups.setdefault(r.group_no, []).append(r)

    created = 0
    with transaction.atomic():
        existing = {
            d.group_no: d
            for d in Dispute.objects.select_for_update().filter(
                project=project, reconcile_date=reconcile_date, group_no__in=groups.keys()
            )
        }
        for group_no, rows in groups.items():
            rep = next((r for r in rows if r.a_id), rows[0])  # A 侧代表行
            amount = rep.a.amount if rep.a_id else (rep.b.amount if rep.b_id else 0)
            dispute = existing.get(group_no)
            if dispute is None:
                dispute = Dispute.objects.create(
                    project=project,
                    reconcile_date=reconcile_date,
                    type=rep.status,
                    a=rep.a,
                    b=rep.b,
                    group_no=group_no,
                    amount=amount,
                    status=Dispute.Status.OPEN,
                )
                HandleLog.objects.create(
                    dispute=dispute, action=HandleLog.Action.REGISTERED,
                    from_status="", to_status=Dispute.Status.OPEN,
                )
                created += 1
            elif dispute.status == Dispute.Status.CLOSED:
                # 已处理的差异：保留原记录，标记被重对覆盖（不新建，保持追溯闭环）
                dispute.superseded = True
                dispute.save(update_fields=["superseded", "updated_at"])
                HandleLog.objects.create(
                    dispute=dispute, action=HandleLog.Action.CLOSED_BY_RERUN,
                    from_status=dispute.status, to_status=dispute.status,
                    remark="重对后该组差异再次出现，原处理保留",
                )
            else:
                # open/processing：刷新字段（可能重对后金额变化）+ reopened 留痕
                dispute.type = rep.status
                dispute.a = rep.a
                dispute.b = rep.b
                dispute.amount = amount
                dispute.superseded = False
                dispute.save()
                HandleLog.objects.create(
                    dispute=dispute, action=HandleLog.Action.REOPENED,
                    from_status=dispute.status, to_status=dispute.status,
                    remark="重对刷新差异数据",
                )
    return created
