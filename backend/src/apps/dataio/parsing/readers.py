"""readers：xlsx/csv/txt → (headers, rows)。纯函数，无 DB。"""
from __future__ import annotations

import csv
import io

FALLBACK_ENCODING = "gb18030"  # 银行/渠道文件常见中文编码兜底


class ReadError(Exception):
    """文件层面不可读（编码/表头行号/空文件），错误直接面向用户。"""


def read(file_bytes: bytes, rule) -> tuple[list[str], list[list[str]]]:
    """按 rule.file_format 分派读取；返回 (表头列表, 数据行列表)。"""
    fmt = getattr(rule, "file_format", "csv")
    if fmt == "xlsx":
        return _read_xlsx(file_bytes, rule)
    return _read_delimited(file_bytes, rule)


def _decode(file_bytes: bytes, encoding: str) -> str:
    """按规则编码解码；utf-8 系失败自动回退 gb18030 重试一次。"""
    try:
        return file_bytes.decode(encoding or "utf-8-sig")
    except (UnicodeDecodeError, LookupError):
        try:
            return file_bytes.decode(FALLBACK_ENCODING)
        except UnicodeDecodeError as e:
            raise ReadError(
                f"无法解码文件：编码 {encoding!r} 与兜底编码 {FALLBACK_ENCODING} 均失败，请确认文件编码"
            ) from e


def _split_records(text: str) -> list[list[str]]:
    return [row for row in csv.reader(io.StringIO(text)) if any((c or "").strip() for c in row)]


def _read_delimited(file_bytes: bytes, rule) -> tuple[list[str], list[list[str]]]:
    text = _decode(file_bytes, rule.encoding)
    delimiter = rule.delimiter or ","
    if delimiter == "\\t":
        delimiter = "\t"
    records = _split_records_text(text, delimiter)
    return _cut_header(records, rule.header_row)


def _split_records_text(text: str, delimiter: str) -> list[list[str]]:
    return [
        [(c or "").strip() for c in row]
        for row in csv.reader(io.StringIO(text), delimiter=delimiter)
        if any((c or "").strip() for c in row)
    ]


def _cut_header(records: list[list[str]], header_row: int) -> tuple[list[str], list[list[str]]]:
    idx = (header_row or 1) - 1
    if idx < 0 or len(records) <= idx:
        raise ReadError(f"文件为空或表头行号 {header_row} 超出实际行数（{len(records)} 行）")
    headers = [(h or "").strip() for h in records[idx]]
    return headers, records[idx + 1 :]


def _read_xlsx(file_bytes: bytes, rule) -> tuple[list[str], list[list[str]]]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 —— 任何 xlsx 解析失败都归一为 ReadError
        raise ReadError(f"Excel 文件无法解析：{e}") from e
    try:
        ws = wb.active
        records: list[list[str]] = []
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else (v if isinstance(v, str) else str(v)).strip() for v in row]
            if any(vals):
                records.append(vals)
    finally:
        wb.close()
    return _cut_header(records, rule.header_row)
