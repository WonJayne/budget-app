"""Explicit period filtering helpers for cash-flow views."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Literal

from .models import Transaction

PeriodMode = Literal["all", "year", "month"]


@dataclass(frozen=True)
class PeriodFilter:
    mode: PeriodMode
    year: int | None = None
    month: int | None = None

    def includes(self, transaction: Transaction) -> bool:
        if self.mode == "all":
            return True
        if self.year is None or transaction.date.year != self.year:
            return False
        if self.mode == "month":
            return self.month is not None and transaction.date.month == self.month
        return True

    @property
    def label(self) -> str:
        if self.mode == "all":
            return "All transactions"
        if self.mode == "year":
            return f"Year {self.year}"
        if self.year is None or self.month is None:
            return "Selected month"
        return f"{calendar.month_name[self.month]} {self.year}"


def default_period_filter(transactions: Iterable[Transaction], today: date | None = None) -> PeriodFilter:
    """Default to the most recent transaction month, or the current month for empty state."""
    rows = tuple(transactions)
    if rows:
        latest = max(transaction.date for transaction in rows)
        return PeriodFilter(mode="month", year=latest.year, month=latest.month)
    current = today or date.today()
    return PeriodFilter(mode="month", year=current.year, month=current.month)


def entry_date_for_period(period: PeriodFilter | None, today: date | None = None) -> date:
    """Choose an entry date inside the selected period."""
    current = today or date.today()
    if period is None or period.mode == "all" or period.year is None:
        return current
    if period.mode == "month" and period.month is not None:
        return date(period.year, period.month, 1)
    return current if period.year == current.year else date(period.year, 1, 1)


def filter_transactions_by_period(transactions: Iterable[Transaction], period: PeriodFilter) -> tuple[Transaction, ...]:
    return tuple(transaction for transaction in transactions if period.includes(transaction))


def available_years(transactions: Iterable[Transaction], fallback: date | None = None) -> tuple[int, ...]:
    years = {transaction.date.year for transaction in transactions}
    if not years:
        years.add((fallback or date.today()).year)
    return tuple(sorted(years))
