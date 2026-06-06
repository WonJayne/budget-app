"""Summary aggregation for the visualisation page."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import FlowType, Transaction, flow_type_for_amount
from .periods import PeriodFilter


@dataclass(frozen=True)
class CashFlowTotals:
    total_inflow: float
    total_outflow: float
    balance: float

    @property
    def potential_savings(self) -> float:
        return self.balance if self.balance > 0 else 0.0

    @property
    def deficit(self) -> float:
        return abs(self.balance) if self.balance < 0 else 0.0


@dataclass(frozen=True)
class SummaryRow:
    flow_type: FlowType
    category: str
    owner: str
    total_amount: float
    share_of_outflows: float


@dataclass(frozen=True)
class YearlyOverviewRow:
    month: int
    total_inflow: float
    total_outflow: float
    balance: float

    @property
    def potential_savings(self) -> float:
        return self.balance if self.balance > 0 else 0.0

    @property
    def deficit(self) -> float:
        return abs(self.balance) if self.balance < 0 else 0.0


def included_transactions(
    transactions: Iterable[Transaction],
    *,
    include_inflows: bool,
    include_ignored: bool,
    month: str | None = None,
    owner: str | None = None,
    currency: str | None = None,
    period: PeriodFilter | None = None,
) -> tuple[Transaction, ...]:
    rows = []
    for transaction in transactions:
        if flow_type_for_amount(transaction.amount) is None:
            continue
        if not include_ignored and transaction.ignored:
            continue
        if period is not None and not period.includes(transaction):
            continue
        if period is None and month and transaction.date.strftime("%Y-%m") != month:
            continue
        if owner and transaction.owner != owner:
            continue
        if currency and transaction.currency != currency:
            continue
        if not include_inflows and transaction.amount > 0:
            continue
        rows.append(transaction)
    return tuple(rows)


def cash_flow_totals(transactions: Iterable[Transaction]) -> CashFlowTotals:
    total_inflow = sum(transaction.amount for transaction in transactions if transaction.amount > 0)
    total_outflow = sum(abs(transaction.amount) for transaction in transactions if transaction.amount < 0)
    return CashFlowTotals(total_inflow=total_inflow, total_outflow=total_outflow, balance=total_inflow - total_outflow)


def summarize_transactions(
    transactions: Iterable[Transaction],
    *,
    include_inflows: bool,
    include_ignored: bool,
    month: str | None = None,
    owner: str | None = None,
    currency: str | None = None,
    period: PeriodFilter | None = None,
) -> tuple[SummaryRow, ...]:
    included = included_transactions(
        transactions,
        month=month,
        owner=owner,
        currency=currency,
        include_inflows=include_inflows,
        include_ignored=include_ignored,
        period=period,
    )
    totals: defaultdict[tuple[FlowType, str, str], float] = defaultdict(float)
    outflow_total = sum(abs(transaction.amount) for transaction in included if transaction.amount < 0)
    for transaction in included:
        flow_type = flow_type_for_amount(transaction.amount)
        if flow_type is None:
            continue
        category = transaction.category or ("Uncategorised inflow" if flow_type == "inflow" else "Uncategorised outflow")
        owner_name = transaction.owner or ("Unassigned inflow" if flow_type == "inflow" else "Unassigned outflow")
        totals[(flow_type, category, owner_name)] += transaction.amount

    rows = []
    for (flow_type, category, owner_name), total in sorted(totals.items()):
        share = abs(total) / outflow_total if flow_type == "outflow" and outflow_total else 0.0
        rows.append(SummaryRow(flow_type, category, owner_name, total, share))
    return tuple(rows)


def yearly_overview(transactions: Iterable[Transaction], year: int, *, currency: str | None = None, include_ignored: bool = False) -> tuple[YearlyOverviewRow, ...]:
    rows: list[YearlyOverviewRow] = []
    for month_number in range(1, 13):
        included = included_transactions(
            transactions,
            period=PeriodFilter(mode="month", year=year, month=month_number),
            owner=None,
            currency=currency,
            include_inflows=True,
            include_ignored=include_ignored,
        )
        totals = cash_flow_totals(included)
        rows.append(YearlyOverviewRow(month=month_number, total_inflow=totals.total_inflow, total_outflow=totals.total_outflow, balance=totals.balance))
    return tuple(rows)
