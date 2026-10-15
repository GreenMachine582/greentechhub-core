"""exports: rows as CSV text (with a BOM by default) and csv_value's cell
formatting, framework-free."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from greentechhub_core.exports import BOM, csv_text, csv_value


def test_csv_text_starts_with_a_bom_and_quotes_cells():
    text = csv_text([["date", "notes"], ["2024-08-01", 'a "quoted", note'], ["2025–26", ""]])
    assert text.startswith(BOM)
    assert list(csv.reader(io.StringIO(text.removeprefix(BOM)))) == [
        ["date", "notes"], ["2024-08-01", 'a "quoted", note'], ["2025–26", ""]]


def test_csv_text_without_a_bom():
    assert csv_text([["a", "b"]], bom=False) == "a,b\r\n"


def test_csv_text_takes_any_iterables():
    assert csv_text(((n, n * 2) for n in range(2)), bom=False) == "0,0\r\n1,2\r\n"


def test_csv_value():
    assert csv_value(None) == ""
    assert csv_value(Decimal("12.50")) == "12.5" and csv_value(Decimal("1E+2")) == "100"
    assert csv_value(date(2024, 8, 1)) == "2024-08-01"
    assert csv_value(datetime(2024, 8, 1, 9, 30)) == "2024-08-01T09:30:00"
    assert csv_value(7) == "7"
