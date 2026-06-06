"""Summary aggregation for the visualisation page."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import Transaction


@dataclass(frozen=True)
class SummaryRow:
    category: str
    owner: str
    total_amount: float
    share_of_expenses: float


def summarize_transactions(
    transactions: Iterable[Transaction],
    *,
    month: str | None,
    owner: str | None,
    currency: str | None,
    include_income: bool,
    include_ignored: bool,
) -> tuple[SummaryRow, ...]:
    totals: defaultdict[tuple[str, str], float] = defaultdict(float)
    expense_total = 0.0
    for transaction in transactions:
        if not include_ignored and transaction.ignored:
            continue
        if month and transaction.date.strftime("%Y-%m") != month:
            continue
        if owner and transaction.owner != owner:
            continue
        if currency and transaction.currency != currency:
            continue
        if not include_income and transaction.amount > 0:
            continue
        category = transaction.category or ("Income" if transaction.amount > 0 else "Uncategorised")
        owner_name = transaction.owner or "Unassigned"
        totals[(category, owner_name)] += transaction.amount
        if transaction.amount < 0:
            expense_total += abs(transaction.amount)

    rows = []
    for (category, owner_name), total in sorted(totals.items()):
        share = abs(total) / expense_total if total < 0 and expense_total else 0.0
        rows.append(SummaryRow(category, owner_name, total, share))
    return tuple(rows)
