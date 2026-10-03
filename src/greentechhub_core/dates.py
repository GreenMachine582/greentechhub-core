"""dates — fiscal years, see docs/modules.md#dates.

A fiscal year starts on the 1st of `start_month` and runs twelve months; the
default, July, is Australia's. It is identified by the year it STARTS in —
FY 2024 runs 1 Jul 2024 to 30 Jun 2025 — which is why its label names both
years ("2024–25"): a bare "FY2025" reads as the year it ends in to many.
greentechhub-ui's gth_date_range(fy_start_month=...) presets use the same
rule client-side.
"""

from datetime import date, timedelta


def _check(start_month: int) -> None:
    if not 1 <= start_month <= 12:
        raise ValueError(f"start_month must be 1-12, got {start_month!r}")


def fiscal_year(d: date, start_month: int = 7) -> int:
    """The fiscal year containing `d`, as the year it starts in:
    fiscal_year(date(2025, 3, 1)) == 2024. start_month=1 is the calendar
    year."""
    _check(start_month)
    return d.year if d.month >= start_month else d.year - 1


def fiscal_year_bounds(fy: int, start_month: int = 7) -> tuple[date, date]:
    """The first and last day of fiscal year `fy`, inclusive:
    (date(2024, 7, 1), date(2025, 6, 30)) for FY 2024."""
    _check(start_month)
    start = date(fy, start_month, 1)
    next_start = date(fy + 1, start_month, 1)
    return start, next_start - timedelta(days=1)


def fiscal_year_label(fy: int, start_month: int = 7) -> str:
    """"2024–25" (en dash, two-digit end year; "1999–00" across a century),
    or just "2024" when the fiscal year is the calendar year."""
    _check(start_month)
    if start_month == 1:
        return str(fy)
    return f"{fy}–{(fy + 1) % 100:02d}"
