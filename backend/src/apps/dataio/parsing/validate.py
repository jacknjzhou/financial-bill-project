"""validate：整批校验入口。任一行有错 → ok=False 且不返回任何数据行
（回滚语义的函数层体现：不产生部分入库的脏数据）。"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import mapping, readers

# 各目标表必填字段（缺一该行报错）
REQUIRED: dict[str, list[str]] = {
    "payment": ["order_no", "biz_type", "amount", "status", "tx_time"],
    "clearing": ["channel_order_no", "amount", "status", "tx_time"],
    "settlement": ["account", "fee_item", "amount", "settle_date"],
}

# 键唯一性（重复键整批拒绝，防脏数据）
KEY_FIELDS: dict[str, list[str]] = {
    "payment": ["order_no", "pay_no"],
    "clearing": ["channel_order_no"],
    "settlement": ["account", "fee_item", "settle_date"],
}


@dataclass
class ParseResult:
    ok: bool
    total: int
    rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)  # [{row_no, col, reason}]


def parse_file(file_bytes: bytes, rule) -> ParseResult:
    errors: list[dict] = []

    headers, raw_rows = readers.read(file_bytes, rule)

    # 表头校验：column_map 引用的文件列必须存在；必填标准字段必须有映射
    mapped: dict[str, str] = {}
    for col, fld in (rule.column_map or {}).items():
        col, fld = (col or "").strip(), (fld or "").strip()
        if col and fld:
            mapped[fld] = col
    for fld, col in mapped.items():
        if col not in headers:
            errors.append({"row_no": None, "col": col, "reason": "表头缺少该映射列"})
    for fld in REQUIRED.get(rule.target, []):
        if fld not in mapped:
            errors.append({"row_no": None, "col": fld, "reason": "必填字段未配置列映射"})

    key_fields = KEY_FIELDS.get(rule.target, [])
    seen: dict[tuple, int] = {}
    rows: list[dict] = []

    for idx, raw in enumerate(raw_rows, start=1):
        try:
            row = mapping.map_row(headers, raw, rule)
        except mapping.MappingError as e:
            errors.append({"row_no": idx, "col": e.col, "reason": e.reason})
            continue

        for fld in REQUIRED.get(rule.target, []):
            if row.get(fld) in (None, ""):
                errors.append({"row_no": idx, "col": fld, "reason": "必填字段缺失"})

        key = tuple(str(row.get(f) or "") for f in key_fields)
        if key_fields:
            if key in seen:
                errors.append(
                    {"row_no": idx, "col": "+".join(key_fields), "reason": f"键与第 {seen[key]} 行重复"}
                )
                errors.append(
                    {"row_no": seen[key], "col": "+".join(key_fields), "reason": "存在重复键"}
                )
            else:
                seen[key] = idx
        rows.append(row)

    total = len(raw_rows)
    return ParseResult(ok=not errors, total=total, rows=rows if not errors else [], errors=errors)
