"""解析任务：InFile → parsing.parse_file → 源数据表（整批原子入库/失败留痕）。"""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from apps.dataio.parsing import validate

logger = logging.getLogger(__name__)

BULK_BATCH = 1000


def _store_path(instance, name: str) -> str:
    from django.conf import settings as dj_settings
    from pathlib import Path

    root = Path(dj_settings.FILES_ROOT)
    return str(root / str(instance.fetch_task_id) / str(instance.created_date) / name)


@shared_task
def parse_file_task(in_file_id: int) -> str:
    from apps.dataio.models import ClearingData, InFile, PaymentData, SettlementData

    in_file = InFile.objects.select_related("fetch_task", "fetch_task__parse_rule", "fetch_task__channel", "fetch_task__account").get(pk=in_file_id)
    in_file.status = InFile.Status.PARSING
    in_file.save(update_fields=["status", "updated_at"])

    rule = in_file.fetch_task.parse_rule
    try:
        content = _read_storage(in_file)
        result = validate.parse_file(content, rule)
    except Exception as e:  # noqa: BLE001 —— 解析层之外的意外错误也归一为 failed（不丢状态）
        logger.exception("parse_file_task failed: InFile#%s", in_file_id)
        in_file.status = InFile.Status.FAILED
        in_file.error_msg = f"解析异常：{e}"
        in_file.save(update_fields=["status", "error_msg", "updated_at"])
        return "failed"

    in_file.total_rows = result.total
    if not result.ok:
        lines = [f"行 {e['row_no']} 列 {e['col']}: {e['reason']}" if e["row_no"] else f"表头 列 {e['col']}: {e['reason']}" for e in result.errors[:100]]
        in_file.status = InFile.Status.FAILED
        in_file.error_msg = "\n".join(lines)
        in_file.save(update_fields=["status", "total_rows", "error_msg", "updated_at"])
        return "failed"

    task = in_file.fetch_task
    biz_map = _biz_type_map(result.rows)

    with transaction.atomic():
        if rule.target == "payment":
            objs = [
                PaymentData(
                    order_no=r["order_no"], pay_no=r.get("pay_no") or "",
                    channel=task.channel, account=task.account,
                    biz_type=biz_map.get(r.get("biz_type")),
                    amount=r["amount"], status=r["status"],
                    tx_time=r.get("tx_time"), tx_date=r.get("tx_date"),
                    reconcile_date=r["reconcile_date"], file=in_file,
                )
                for r in result.rows
            ]
            PaymentData.objects.bulk_create(objs, batch_size=BULK_BATCH)
        elif rule.target == "clearing":
            objs = [
                ClearingData(
                    channel_order_no=r["channel_order_no"], order_no=r.get("order_no") or "",
                    channel=task.channel, account=task.account,
                    biz_type=biz_map.get(r.get("biz_type")),
                    amount=r["amount"], status=r["status"],
                    tx_time=r.get("tx_time"), tx_date=r.get("tx_date"),
                    reconcile_date=r["reconcile_date"], file=in_file,
                )
                for r in result.rows
            ]
            ClearingData.objects.bulk_create(objs, batch_size=BULK_BATCH)
        else:
            objs = [
                SettlementData(
                    channel=task.channel, account=task.account,
                    fee_item=r["fee_item"], amount=r["amount"],
                    fee_amount=r.get("fee_amount"), actual_amount=r.get("actual_amount"),
                    settle_date=r["settle_date"], reconcile_date=r["reconcile_date"], file=in_file,
                )
                for r in result.rows
            ]
            SettlementData.objects.bulk_create(objs, batch_size=BULK_BATCH)

    in_file.status = InFile.Status.PARSED
    in_file.save(update_fields=["status", "total_rows", "updated_at"])
    return "parsed"


def _read_storage(in_file) -> bytes:
    from pathlib import Path

    return Path(in_file.storage_path).read_bytes()


def _biz_type_map(rows: list[dict]) -> dict:
    """biz_type 文本 → BizType 行（按 code 匹配；未登记的编码置空，不阻塞入库）。"""
    from apps.meta.models import BizType

    codes = {r.get("biz_type") for r in rows if r.get("biz_type")}
    if not codes:
        return {}
    return {b.code: b for b in BizType.objects.filter(code__in=codes)}
