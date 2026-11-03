"""T7 解析引擎纯函数测试（rule 为不落库的 ParseRule 实例；无 DB）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.rules.models import ParseRule

FIXTURES = Path(__file__).parent / "fixtures" / "files"

COLUMN_MAP = {
    "商户单号": "order_no",
    "支付单号": "pay_no",
    "渠道单号": "channel_order_no",
    "业务类型": "biz_type",
    "金额": "amount",
    "手续费": "fee_amount",
    "状态": "status",
    "交易时间": "tx_time",
}


def make_rule(**overrides) -> ParseRule:
    params = dict(
        name="测试规则",
        target="payment",
        file_format="csv",
        encoding="utf-8-sig",
        delimiter=",",
        header_row=1,
        column_map=dict(COLUMN_MAP),
        value_maps={"status": {"成功": "SUCCESS", "失败": "FAIL"}},
        amount_scale=100,
        time_format="%Y-%m-%d %H:%M:%S",
    )
    params.update(overrides)
    return ParseRule(**params)


def xlsx_bytes(header_row: int = 1, rows: list[list] | None = None) -> bytes:
    """conftest 工厂：构造内存 xlsx（带表头行号场景）。"""
    import io

    from openpyxl import Workbook

    if rows is None:
        rows = [
            ["9001", "pay9001", "ch9001", "INCOME", "88.40", "0.26", "成功", "2026-10-31 15:00:00"],
            ["9002", "pay9002", "ch9002", "INCOME", "99.50", "0.29", "成功", "2026-10-31 16:00:00"],
            ["9003", "pay9003", "ch9003", "REFUND", "11.11", "0.03", "失败", "2026-10-31 17:00:00"],
        ]
    wb = Workbook()
    ws = wb.active
    if header_row > 1:
        ws.append([f"XX渠道交易明细（导出时间 2026-11-01 02:00:00）"])  # noqa: F541
    ws.append(list(COLUMN_MAP.keys()))
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestReadersAndMapping:
    def test_csv(self):
        from apps.dataio.parsing import validate

        result = validate.parse_file((FIXTURES / "good.csv").read_bytes(), make_rule())
        assert result.ok, result.errors
        assert result.total == 3
        assert len(result.rows) == 3
        first = result.rows[0]
        assert first["order_no"] == "1001"
        assert first["amount"] == 10050  # 100.50 元 → 10050 分
        assert first["fee_amount"] == 30
        assert first["status"] == "SUCCESS"  # 值映射

    def test_txt_delimiter(self):
        from apps.dataio.parsing import validate

        rule = make_rule(file_format="txt", delimiter="\t")
        result = validate.parse_file((FIXTURES / "good.txt").read_bytes(), rule)
        assert result.ok, result.errors
        assert result.total == 3
        assert result.rows[0]["amount"] == 30010

    def test_xlsx(self):
        from apps.dataio.parsing import validate

        rule = make_rule(file_format="xlsx", header_row=2)
        result = validate.parse_file(xlsx_bytes(header_row=2), rule)
        assert result.ok, result.errors
        assert result.total == 3
        assert result.rows[0]["amount"] == 8840

    def test_value_maps(self):
        from apps.dataio.parsing import validate

        result = validate.parse_file((FIXTURES / "good.csv").read_bytes(), make_rule())
        assert result.rows[2]["status"] == "FAIL"  # 失败 → FAIL

    def test_amount_precision(self):
        """审查重点 4：0.1/0.2/0.3 元 → 10/20/30 分，无浮点漂移。"""
        from apps.dataio.parsing import validate

        result = validate.parse_file((FIXTURES / "money.csv").read_bytes(), make_rule())
        assert result.ok, result.errors
        assert [r["amount"] for r in result.rows] == [10, 20, 30]


class TestValidationFailures:
    def test_header_mismatch(self):
        """审查重点 1：缺"金额"列 → ok=False，错误指向列名。"""
        from apps.dataio.parsing import validate

        result = validate.parse_file((FIXTURES / "bad_header.csv").read_bytes(), make_rule())
        assert not result.ok
        assert result.rows == []  # 整批回滚语义：有错误就不返回数据
        assert any(e["col"] == "金额" for e in result.errors)

    def test_bad_row(self):
        from apps.dataio.parsing import validate

        result = validate.parse_file((FIXTURES / "bad_row.csv").read_bytes(), make_rule())
        assert not result.ok
        assert result.errors[0]["row_no"] == 2
        assert "金额" in result.errors[0]["col"] or result.errors[0]["col"] == "amount"

    def test_duplicate_keys(self):
        """审查重点 2：同 order_no+pay_no 两行 → 两行行号都在 errors。"""
        from apps.dataio.parsing import validate

        result = validate.parse_file((FIXTURES / "dupe_keys.csv").read_bytes(), make_rule())
        assert not result.ok
        row_nos = {e["row_no"] for e in result.errors}
        assert {1, 2} <= row_nos

    def test_crossday(self):
        """审查重点 3（解析侧）：UTC+8 本地日期切分 reconcile_date。"""
        from apps.dataio.parsing import validate

        result = validate.parse_file((FIXTURES / "crossday.csv").read_bytes(), make_rule())
        assert result.ok, result.errors
        dates = [r["reconcile_date"] for r in result.rows]
        assert str(dates[0]) == "2026-10-31"
        assert str(dates[1]) == "2026-11-01"
        # tx_time 落库为 UTC
        assert result.rows[0]["tx_time"].utcoffset() is not None
