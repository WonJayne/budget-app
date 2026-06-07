"""Filtering helpers for the editable all-entries ledger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .models import FlowType, Transaction
from .periods import PeriodFilter

LedgerSourceFilter = Literal["all", "csv", "manual"]
LedgerFlowFilter = Literal["all", "inflow", "outflow", "transfer", "transfer_any", "transfer_in", "transfer_out"]
LedgerStatusFilter = Literal["all", "classified", "unclassified", "ignored"]


@dataclass(frozen=True)
class LedgerFilters:
    period: PeriodFilter
    source: LedgerSourceFilter = "all"
    flow_type: LedgerFlowFilter = "all"
    owner: str = "all"
    category: str = "all"
    status: LedgerStatusFilter = "all"
    import_source: str = "all"


def transaction_entry_source(transaction: Transaction) -> Literal["csv", "manual"]:
    """Return the user-facing source label for a transaction."""
    if transaction.entry_source == "manual" or transaction.source_kind == "manual":
        return "manual"
    return "csv"


def filter_ledger_transactions(transactions: Iterable[Transaction], filters: LedgerFilters) -> tuple[Transaction, ...]:
    """Filter transactions for the editable ledger."""
    rows: list[Transaction] = []
    for transaction in transactions:
        if not filters.period.includes(transaction):
            continue
        entry_source = transaction_entry_source(transaction)
        if filters.source != "all" and entry_source != filters.source:
            continue
        if filters.import_source != "all" and transaction.stable_import_source != filters.import_source:
            continue
        flow_type = transaction.flow_type
        if filters.flow_type == "transfer_any":
            if flow_type != "transfer":
                continue
        elif filters.flow_type == "transfer_in":
            if flow_type != "transfer" or transaction.amount <= 0:
                continue
        elif filters.flow_type == "transfer_out":
            if flow_type != "transfer" or transaction.amount >= 0:
                continue
        elif filters.flow_type != "all" and flow_type != filters.flow_type:
            continue
        if filters.owner != "all" and transaction.owner != filters.owner:
            continue
        if filters.category != "all" and transaction.category != filters.category:
            continue
        if filters.status == "classified" and (transaction.ignored or not transaction.category or not transaction.owner):
            continue
        if filters.status == "unclassified" and (transaction.ignored or (transaction.category and transaction.owner)):
            continue
        if filters.status == "ignored" and not transaction.ignored:
            continue
        rows.append(transaction)
    return tuple(sorted(rows, key=lambda tx: (tx.date, tx.description, tx.id), reverse=True))
