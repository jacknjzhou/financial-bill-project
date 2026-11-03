"""mapping：原始行 → 标准字段 dict（列映射 + 值映射 + 金额转分 + 时间解析）。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

AMOUNT_FIELDS = {"amount", "fee_amount", "actual_amount"}
TIME_FIELDS = {"tx_time"}
DATE_FIELDS = {"settle_date"}

# 派生字段：tx_date（本地日期）、reconcile_date（对账日期）


class MappingError(Exception):
    """单行单列映射失败，携带列名与面向用户的原因。"""

    def __init__(self, col: str, reason: str):
        super().__init__(f"{col}: {reason}")
        self.col = col
        self.reason = reason


def _to_cents(raw: str, amount_scale: int, col: str) -> int:
    """金额文本 → 分（int）。必须 Decimal + quantize：int() 截断会把
    三位小数费用项静默丢分、二进制浮点引入 ±1 分漂移。"""
    try:
        value = Decimal(raw.strip())
    except InvalidOperation as e:
        raise MappingError(col, f"金额格式错误：{raw!r}") from e
    cents = (value * (amount_scale or 100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def _parse_time(raw: str, time_format: str, col: str) -> datetime:
    """按规则格式解析 → 本地时区（Asia/Shanghai）→ UTC。"""
    try:
        naive = datetime.strptime(raw.strip(), time_format or "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise MappingError(col, f"时间格式错误：{raw!r}（期望 {time_format}）") from e
    return naive.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def _parse_date(raw: str, col: str) -> date:
    text = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise MappingError(col, f"日期格式错误：{raw!r}（期望 YYYY-MM-DD）")


def map_row(headers: list[str], row: list[str], rule) -> dict:
    """单行映射。未知列忽略；column_map 中文件列名或标准字段为空串的项忽略。

    产出标准字段 + 派生字段（tx_date / reconcile_date）：
    - payment/clearing：reconcile_date = tx_time 的本地（UTC+8）日期；
    - settlement：reconcile_date = settle_date。
    """
    by_col: dict[str, str] = {}
    for i, h in enumerate(headers):
        h = (h or "").strip()
        if h and h not in by_col:
            by_col[h] = (row[i] if i < len(row) else "").strip()

    out: dict = {}
    for col, field in (rule.column_map or {}).items():
        col = (col or "").strip()
        field = (field or "").strip()
        if not col or not field:
            continue  # 空串 = 忽略该列
        raw = by_col.get(col, "")
        vm = (rule.value_maps or {}).get(field)
        if vm and raw in vm:
            raw = str(vm[raw])

        if field in AMOUNT_FIELDS:
            out[field] = None if raw == "" else _to_cents(raw, rule.amount_scale, col)
        elif field in TIME_FIELDS:
            out[field] = None if raw == "" else _parse_time(raw, rule.time_format, col)
        elif field in DATE_FIELDS:
            out[field] = None if raw == "" else _parse_date(raw, col)
        else:
            out[field] = raw

    if out.get("tx_time") is not None:
        local = out["tx_time"].astimezone(LOCAL_TZ)
        out["tx_date"] = local.date()
        out["reconcile_date"] = local.date()
    if out.get("settle_date") is not None:
        out["reconcile_date"] = out["settle_date"]
    return out
