"""exports — rows as CSV text, framework-free: what a web download
(greentechhub-fastapi's csv_download) and a CLI's export both write.

    rows = [HEADER, *([csv_value(t.date), csv_value(t.amount), t.notes] for t in items)]
    Path("transactions.csv").write_text(csv_text(rows), encoding="utf-8")
"""

import csv
import io
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

#: A UTF-8 byte-order mark. Excel opens a CSV without one as Windows-1252, so
#: UTF-8 text such as an en dash ("2025–26") shows up as "2025â€“26". With it,
#: Excel, Numbers and LibreOffice all read UTF-8; pandas reads it with
#: encoding="utf-8-sig".
BOM = "﻿"


def csv_text(rows: Iterable[Iterable[Any]], *, bom: bool = True) -> str:
    """`rows` (the header first) as CSV text, starting with BOM unless
    `bom=False` (for a consumer that doesn't want one, e.g. a pipe into
    another program). Cells go through csv's own quoting; pass csv_value
    for Decimals and dates."""
    buffer = io.StringIO()
    if bom:
        buffer.write(BOM)
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue()


def csv_value(value: Any) -> str:
    """`value` as a CSV cell: "" for None, a Decimal at full precision with
    trailing zeros trimmed and never in E-notation (12.50 → "12.5",
    1E+2 → "100"), a date or datetime in ISO format, anything else str()."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value.normalize():f}"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
