"""Summary aggregation for the visualisation page."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import FlowType, Transaction
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
class TransferSummaryRow:
    category: str
    owner: str
    count: int
    transfer_inflow: float
    transfer_outflow: float
    net_movement: float
    absolute_movement: float

    @property
    def net_amount(self) -> float:
        return self.net_movement


@dataclass(frozen=True)
class YearlyOverviewRow:
    month: int
    total_inflow: float
    total_outflow: float
    balance: float
    transfer_count: int = 0
    transfer_absolute_movement: float = 0.0
    transfer_net_movement: float = 0.0

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
    include_transfers: bool = False,
) -> tuple[Transaction, ...]:
    rows = []
    for transaction in transactions:
        flow_type = transaction.flow_type
        if flow_type is None:
            continue
        if flow_type == "transfer" and not include_transfers:
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
        if not include_inflows and flow_type == "inflow":
            continue
        rows.append(transaction)
    return tuple(rows)


def cash_flow_totals(transactions: Iterable[Transaction]) -> CashFlowTotals:
    total_inflow = sum(transaction.amount for transaction in transactions if transaction.flow_type == "inflow")
    total_outflow = sum(abs(transaction.amount) for transaction in transactions if transaction.flow_type == "outflow")
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
        include_transfers=False,
    )
    totals: defaultdict[tuple[FlowType, str, str], float] = defaultdict(float)
    outflow_total = sum(abs(transaction.amount) for transaction in included if transaction.flow_type == "outflow")
    for transaction in included:
        flow_type = transaction.flow_type
        if flow_type is None or flow_type == "transfer":
            continue
        category = transaction.category or ("Uncategorised inflow" if flow_type == "inflow" else "Uncategorised outflow")
        owner_name = transaction.owner or ("Unassigned inflow" if flow_type == "inflow" else "Unassigned outflow")
        totals[(flow_type, category, owner_name)] += transaction.amount

    rows = []
    for (flow_type, category, owner_name), total in sorted(totals.items()):
        share = abs(total) / outflow_total if flow_type == "outflow" and outflow_total else 0.0
        rows.append(SummaryRow(flow_type, category, owner_name, total, share))
    return tuple(rows)


def transfer_summary(transactions: Iterable[Transaction]) -> tuple[TransferSummaryRow, ...]:
    grouped: defaultdict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        if transaction.flow_type == "transfer":
            grouped[(transaction.category or "Internal transfer", transaction.owner or "Unassigned")].append(transaction)
    rows = []
    for (category, owner), group in sorted(grouped.items()):
        rows.append(
            TransferSummaryRow(
                category=category,
                owner=owner,
                count=len(group),
                transfer_inflow=sum(transaction.amount for transaction in group if transaction.amount > 0),
                transfer_outflow=sum(abs(transaction.amount) for transaction in group if transaction.amount < 0),
                net_movement=sum(transaction.amount for transaction in group),
                absolute_movement=sum(abs(transaction.amount) for transaction in group),
            )
        )
    return tuple(rows)


def yearly_overview(transactions: Iterable[Transaction], year: int, *, currency: str | None = None, include_ignored: bool = False) -> tuple[YearlyOverviewRow, ...]:
    rows: list[YearlyOverviewRow] = []
    for month_number in range(1, 13):
        period = PeriodFilter(mode="month", year=year, month=month_number)
        included = included_transactions(
            transactions,
            period=period,
            owner=None,
            currency=currency,
            include_inflows=True,
            include_ignored=include_ignored,
        )
        transfers = included_transactions(
            transactions,
            period=period,
            owner=None,
            currency=currency,
            include_inflows=True,
            include_ignored=include_ignored,
            include_transfers=True,
        )
        transfer_rows = [transaction for transaction in transfers if transaction.flow_type == "transfer"]
        totals = cash_flow_totals(included)
        rows.append(
            YearlyOverviewRow(
                month=month_number,
                total_inflow=totals.total_inflow,
                total_outflow=totals.total_outflow,
                balance=totals.balance,
                transfer_count=len(transfer_rows),
                transfer_absolute_movement=sum(abs(transaction.amount) for transaction in transfer_rows),
                transfer_net_movement=sum(transaction.amount for transaction in transfer_rows),
            )
        )
    return tuple(rows)
