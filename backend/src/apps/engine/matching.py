"""匹配算法（纯函数 + 取数编排）。

消费语义（钉死）：B 按 match_key 建 dict[list] 索引；A 逐行从索引**弹出**
（pop 一行，命中即从索引删除，同键第二条 A 只能配下一行 B 或落 one_a），
杜绝同一条 B 被两条 A 同时命中而撞部分唯一约束。
"""
from __future__ import annotations

import logging
from uuid import uuid4

from django.db import connection

logger = logging.getLogger(__name__)

BULK_BATCH = 1000

# 取数字段映射（标准字段 → 模型字段）
FIELD_MAP = {"biz_type": "biz_type__code"}


def match(a_rows: list[dict], b_rows: list[dict], project) -> list[dict]:
    """a_rows/b_rows：含 id/amount/status/<match_key> 的 dict（DB 行挂在 "row"）。

    返回结果 dict 列表：{status, a, b, match_key, diff_amount, diff_type, biz_type, group_no}。
    """
    key_field = project.match_key
    index: dict[str, list[dict]] = {}
    for b in b_rows:
        index.setdefault(_kv(b, key_field), []).append(b)

    a_set = set(project.a_status_set or [])
    b_set = set(project.b_status_set or [])

    out: list[dict] = []
    for a in a_rows:
        k = _kv(a, key_field)
        group = index.get(k)
        if not group:
            out.append(_single("one_a", a=a, key=k))
            continue
        del index[k]  # 整组消费：命中即从索引删除（同键下一条 A 只能落 one_a 或配下一组）
        out.extend(_compare(a, group, a_set, b_set, k, project))
        continue

    # 剩余未匹配 B
    for k, group in index.items():
        if project.b_sum and len(group) > 1:
            gid = uuid4()
            for b in group:
                out.append(_single("one_b", b=b, key=k, group_no=gid))
        else:
            for b in group:
                out.append(_single("one_b", b=b, key=k))
    return out


def _kv(row: dict, field: str) -> str:
    return str(row.get(field) if row.get(field) is not None else "")


def _single(status: str, a=None, b=None, key: str = "", group_no=None) -> dict:
    return {
        "status": status,
        "a": a,
        "b": b,
        "match_key": key,
        "diff_amount": 0,
        "diff_type": "none",
        "biz_type": (a or b or {}).get("biz_type"),
        "group_no": group_no or uuid4(),
    }


def _compare(a: dict, b_group: list[dict], a_set: set, b_set: set, k: str, project) -> list[dict]:
    """A 与一个 B 组比较：状态集规则 + 金额规则（组内求和按 project.b_sum）。

    统一产出：A 一条 + B 组每行各一条（同 group_no）；差异金额/类型记在 A 行。
    """
    total = sum(b["amount"] for b in b_group)
    status_ok = (not a_set or a.get("status") in a_set) and all(
        (not b_set or b.get("status") in b_set) for b in b_group
    )
    amount_ok = total == a["amount"]

    gid = uuid4()
    results: list[dict] = []

    if status_ok and amount_ok:
        status, diff_amount, diff_type = "match", 0, "none"
    else:
        status = "wrong"
        diff_amount = 0 if amount_ok else total - a["amount"]
        if not amount_ok and not status_ok:
            diff_type = "both"
        elif not amount_ok:
            diff_type = "amount"
        else:
            diff_type = "status"

    a_res = _single(status, a=a, key=k, group_no=gid)
    a_res["diff_amount"] = diff_amount
    a_res["diff_type"] = diff_type
    results.append(a_res)
    for b in b_group:
        results.append(_single(status, b=b, key=k, group_no=gid))
    return results


# ---------- 取数编排 ----------

SOURCE_TABLES = {"payment": "dataio", "clearing": "dataio", "settlement": "dataio"}


def collect_and_match(run) -> dict:
    """claim 后执行：按 (P, date) + 筛选取数 → match() → write() → 计数。"""
    from apps.engine import results
    from apps.dataio.models import ClearingData, PaymentData, SettlementData

    project = run.project
    date = run.reconcile_date

    a_qs = _source_queryset(project.a_source, project.a_filter, project.match_key).filter(reconcile_date=date)
    b_qs = _source_queryset(project.b_source, project.b_filter, project.match_key).filter(reconcile_date=date)

    a_rows = list(a_qs.iterator(chunk_size=1000))
    b_rows = list(b_qs.iterator(chunk_size=1000))

    a_dicts = [_to_dict(r, project.match_key) for r in a_rows]
    b_dicts = [_to_dict(r, project.match_key) for r in b_rows]

    matched = match(a_dicts, b_dicts, project)
    counts = results.write(run, matched)
    return {"a_total": len(a_dicts), "b_total": len(b_dicts), **counts}


def _source_queryset(source: str, filters: list[dict], match_key: str):
    from django.apps import apps as dj_apps

    model = dj_apps.get_model("dataio", {"payment": "PaymentData", "clearing": "ClearingData", "settlement": "SettlementData"}[source])
    qs = model.objects.select_related("biz_type", "channel", "account")
    for cond in filters or []:
        field = FIELD_MAP.get(cond.get("field"), cond.get("field"))
        op, value = cond.get("op"), cond.get("value")
        if op == "eq":
            qs = qs.filter(**{field: value})
        elif op == "in":
            qs = qs.filter(**{f"{field}__in": [v.strip() for v in str(value).split(",") if v.strip()]})
        elif op == "neq":
            qs = qs.exclude(**{field: value})
    return qs.order_by("id")


def _to_dict(obj, match_key: str) -> dict:
    d = {
        "id": obj.pk,
        "amount": obj.amount,
        "status": getattr(obj, "status", None),
        match_key: getattr(obj, match_key, None),
        "biz_type": getattr(obj, "biz_type", None),
        "row": obj,
    }
    if match_key not in d or d[match_key] is None:
        # settlement 等无匹配键字段的源：键取空（由筛选条件约束分组）
        d[match_key] = ""
    return d
