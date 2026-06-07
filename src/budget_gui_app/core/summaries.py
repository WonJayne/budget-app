"""Summary aggregation for the visualisation page."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Literal

from .models import FlowType, Transaction
from .periods import PeriodFilter

TRANSFER_BALANCE_TOLERANCE = 0.01
TransferGroupStatus = Literal["balanced", "unmatched_inflow", "unmatched_outflow", "partial", "single_sided"]


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
class TransferGroupSummary:
    group_id: str
    currency: str
    count: int
    transfer_inflow: float
    transfer_outflow: float
    matched_amount: float
    unmatched_inflow: float
    unmatched_outflow: float
    net_movement: float
    absolute_movement: float
    status: TransferGroupStatus
    category: str
    owner: str

    @property
    def net_amount(self) -> float:
        return self.net_movement

    @property
    def internal_transfer_in(self) -> float:
        return self.transfer_inflow

    @property
    def internal_transfer_out(self) -> float:
        return self.transfer_outflow


TransferSummaryRow = TransferGroupSummary


@dataclass(frozen=True)
class TransferMonitorTotals:
    matched_transfers: float
    unmatched_transfer_inflow: float
    unmatched_transfer_outflow: float
    net_transfer_movement: float
    absolute_transfer_movement: float
    transfer_count: int

    @property
    def internal_transfer_in(self) -> float:
        return self.unmatched_transfer_inflow + self.matched_transfers

    @property
    def internal_transfer_out(self) -> float:
        return self.unmatched_transfer_outflow + self.matched_transfers

    @property
    def matched_internal_transfers(self) -> float:
        return self.matched_transfers

    @property
    def net_internal_movement(self) -> float:
        return self.net_transfer_movement

    @property
    def absolute_internal_movement(self) -> float:
        return self.absolute_transfer_movement


@dataclass(frozen=True)
class YearlyOverviewRow:
    month: int
    total_inflow: float
    total_outflow: float
    balance: float
    transfer_count: int = 0
    transfer_absolute_movement: float = 0.0
    transfer_net_movement: float = 0.0
    matched_transfers: float = 0.0
    unmatched_transfer_inflow: float = 0.0
    unmatched_transfer_outflow: float = 0.0

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


def _transfer_group_label(transaction: Transaction) -> str:
    if transaction.transfer_group_id:
        return transaction.transfer_group_id
    return f"Ungrouped: {transaction.id[:8]}"


def _mixed_or_single(values: Iterable[str | None], fallback: str) -> str:
    unique = {value for value in values if value}
    if not unique:
        return fallback
    if len(unique) == 1:
        return next(iter(unique))
    return "Mixed"


def _transfer_group_status(count: int, transfer_inflow: float, transfer_outflow: float) -> TransferGroupStatus:
    has_inflow = transfer_inflow > TRANSFER_BALANCE_TOLERANCE
    has_outflow = transfer_outflow > TRANSFER_BALANCE_TOLERANCE
    difference = transfer_inflow - transfer_outflow
    if count == 1:
        return "single_sided"
    if has_inflow and has_outflow and abs(difference) <= TRANSFER_BALANCE_TOLERANCE:
        return "balanced"
    if has_inflow and has_outflow:
        return "partial"
    if difference > TRANSFER_BALANCE_TOLERANCE:
        return "unmatched_inflow"
    return "unmatched_outflow"


def transfer_summary(transactions: Iterable[Transaction]) -> tuple[TransferGroupSummary, ...]:
    grouped: defaultdict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        if transaction.flow_type == "transfer":
            grouped[(_transfer_group_label(transaction), transaction.currency)].append(transaction)
    rows = []
    for (group_id, currency), group in sorted(grouped.items()):
        transfer_inflow = sum(transaction.amount for transaction in group if transaction.amount > 0)
        transfer_outflow = sum(abs(transaction.amount) for transaction in group if transaction.amount < 0)
        matched_amount = min(transfer_inflow, transfer_outflow)
        unmatched_inflow = max(transfer_inflow - transfer_outflow, 0.0)
        unmatched_outflow = max(transfer_outflow - transfer_inflow, 0.0)
        rows.append(
            TransferGroupSummary(
                group_id=group_id,
                currency=currency,
                count=len(group),
                transfer_inflow=transfer_inflow,
                transfer_outflow=transfer_outflow,
                matched_amount=matched_amount,
                unmatched_inflow=unmatched_inflow,
                unmatched_outflow=unmatched_outflow,
                net_movement=transfer_inflow - transfer_outflow,
                absolute_movement=transfer_inflow + transfer_outflow,
                status=_transfer_group_status(len(group), transfer_inflow, transfer_outflow),
                category=_mixed_or_single((transaction.category for transaction in group), "Internal transfer"),
                owner=_mixed_or_single((transaction.owner for transaction in group), "Unassigned"),
            )
        )
    return tuple(rows)


def transfer_monitor_totals(groups: Iterable[TransferGroupSummary]) -> TransferMonitorTotals:
    rows = tuple(groups)
    return TransferMonitorTotals(
        matched_transfers=sum(group.matched_amount for group in rows),
        unmatched_transfer_inflow=sum(group.unmatched_inflow for group in rows),
        unmatched_transfer_outflow=sum(group.unmatched_outflow for group in rows),
        net_transfer_movement=sum(group.net_movement for group in rows),
        absolute_transfer_movement=sum(group.absolute_movement for group in rows),
        transfer_count=sum(group.count for group in rows),
    )


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
        transfer_totals = transfer_monitor_totals(transfer_summary(transfers))
        totals = cash_flow_totals(included)
        rows.append(
            YearlyOverviewRow(
                month=month_number,
                total_inflow=totals.total_inflow,
                total_outflow=totals.total_outflow,
                balance=totals.balance,
                transfer_count=transfer_totals.transfer_count,
                transfer_absolute_movement=transfer_totals.absolute_transfer_movement,
                transfer_net_movement=transfer_totals.net_transfer_movement,
                matched_transfers=transfer_totals.matched_transfers,
                unmatched_transfer_inflow=transfer_totals.unmatched_transfer_inflow,
                unmatched_transfer_outflow=transfer_totals.unmatched_transfer_outflow,
            )
        )
    return tuple(rows)
