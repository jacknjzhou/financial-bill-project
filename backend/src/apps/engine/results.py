"""结果写库：同事务 删旧结果 → bulk 1000/批 → 聚合计数（幂等重对的基础）。

计数口径（对账结果页与差错页共用）：
- match_cnt / one_a_cnt / wrong_cnt 按 **A 行**（每组一条）计；
- one_b_cnt 按 **B 行**计（聚合组内每行都算一笔未匹配 B）。
"""
from __future__ import annotations

from uuid import uuid4

from django.db import transaction

BULK_BATCH = 1000


def write(run, matched: list[dict]) -> dict:
    """写匹配结果并返回计数字段 dict（a/b_total 由调用方汇总）。"""
    from apps.engine.models import ReconcileResult

    counts = {"match_cnt": 0, "one_a_cnt": 0, "one_b_cnt": 0, "wrong_cnt": 0}

    with transaction.atomic():
        # 重对先删旧（同事务；PROTECT 只挡跨文件追溯，不挡本日重算）
        ReconcileResult.objects.filter(project=run.project, reconcile_date=run.reconcile_date).delete()

        objs: list[ReconcileResult] = []
        for m in matched:
            status = m["status"]
            has_a = m.get("a") is not None
            if status == "match" and has_a:
                counts["match_cnt"] += 1
            elif status == "one_a":
                counts["one_a_cnt"] += 1
            elif status == "one_b":
                counts["one_b_cnt"] += 1
            elif status == "wrong" and has_a:
                counts["wrong_cnt"] += 1

            a = (m.get("a") or {}).get("row")
            b = (m.get("b") or {}).get("row")
            biz = m.get("biz_type") or getattr(a, "biz_type", None)
            objs.append(
                ReconcileResult(
                    run=run,
                    project=run.project,
                    reconcile_date=run.reconcile_date,
                    status=status,
                    a=a,
                    b=b,
                    match_key=str(m.get("match_key") or ""),
                    diff_amount=m.get("diff_amount") or 0,
                    diff_type=m.get("diff_type") or "none",
                    group_no=m.get("group_no") or uuid4(),
                    biz_type=biz if getattr(biz, "pk", None) else None,
                )
            )

        ReconcileResult.objects.bulk_create(objs, batch_size=BULK_BATCH)

    return counts
