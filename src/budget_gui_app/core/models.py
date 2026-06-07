"""Immutable core models for the budget application."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from datetime import date
from typing import Literal

AssignmentSource = Literal["manual", "rule"] | None
FlowType = Literal["inflow", "outflow", "transfer"]
SourceKind = Literal["imported", "manual"]
EntrySource = Literal["csv", "manual"]


def flow_type_for_amount(amount: float) -> FlowType | None:
    """Return the cash-flow type implied by a transaction amount."""
    if amount > 0:
        return "inflow"
    if amount < 0:
        return "outflow"
    return None


def _generate_id(*parts: str) -> str:
    """Generate a short deterministic identifier from string parts."""
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:16]


def import_source_default(source_file: str | None, entry_source: EntrySource = "csv") -> str | None:
    """Return a stable logical import source for old or partially specified data."""
    if entry_source == "manual":
        return "Manual"
    if source_file:
        return Path(source_file).stem or Path(source_file).name
    return None


@dataclass(frozen=True)
class Transaction:
    id: str
    date: date
    account: str
    description: str
    amount: float
    currency: str
    source_file: str | None = None
    import_source: str | None = None
    cash_flow_type: FlowType | None = None
    category: str | None = None
    owner: str | None = None
    assignment_source: AssignmentSource = None
    ignored: bool = False
    source_kind: SourceKind = "imported"
    entry_source: EntrySource = "csv"
    edited: bool = False
    transfer_group_id: str | None = None
    transfer_note: str | None = None

    def __post_init__(self) -> None:
        if self.import_source is None:
            object.__setattr__(self, "import_source", import_source_default(self.source_file, self.entry_source))
        if self.cash_flow_type is None:
            object.__setattr__(self, "cash_flow_type", flow_type_for_amount(self.amount))

    @staticmethod
    def make_id(date: date, account: str, description: str, amount: float, currency: str) -> str:
        """Derive a deterministic ID from raw transaction fields."""
        return _generate_id(date.isoformat(), account, description, f"{amount:.2f}", currency)

    @staticmethod
    def make_manual_id(date: date, account: str, description: str, amount: float, currency: str, salt: str = "") -> str:
        """Derive a deterministic-looking ID for a user-created manual transaction."""
        return _generate_id("manual", date.isoformat(), account, description, f"{amount:.2f}", currency, salt)

    @property
    def flow_type(self) -> FlowType | None:
        return self.cash_flow_type or flow_type_for_amount(self.amount)

    @property
    def stable_import_source(self) -> str | None:
        return self.import_source or import_source_default(self.source_file, self.entry_source)


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    category: str
    owner: str
    rule_type: FlowType = "outflow"
    priority: int = 0
    import_source: str | None = None

    def matches(self, description: str) -> bool:
        return self.pattern.lower() in description.lower()

    def applies_to_source(self, transaction: Transaction) -> bool:
        return self.import_source is None or self.import_source == transaction.stable_import_source

    @staticmethod
    def make_id(pattern: str, category: str, owner: str, rule_type: FlowType = "outflow", priority: int = 0, salt: str = "", import_source: str | None = None) -> str:
        return _generate_id(pattern.lower(), category, owner, rule_type, str(priority), import_source or "", salt)


@dataclass(frozen=True)
class CategoryStyle:
    category: str
    colour: str | None = None


@dataclass(frozen=True)
class AppProfile:
    owners: tuple[str, ...] = ()
    inflow_categories: tuple[str, ...] = ()
    outflow_categories: tuple[str, ...] = ()
    currencies: tuple[str, ...] = ()
    accounts: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppMetadata:
    schema_version: int = 1
