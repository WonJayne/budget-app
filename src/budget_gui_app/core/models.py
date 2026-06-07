"""Immutable core models for the budget application."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from datetime import date
from typing import Literal

AssignmentSource = Literal["manual", "rule"] | None
FlowType = Literal["inflow", "outflow", "transfer"]
TransferDirection = Literal["in", "out", "none"]
TransferSignScope = Literal["any", "in", "out"]
TransferGroupStrategy = Literal["none", "fixed", "same_day_amount", "same_month_amount"]
BudgetTargetType = Literal["inflow", "outflow", "savings"]
SourceKind = Literal["imported", "manual"]
EntrySource = Literal["csv", "manual"]


def flow_type_for_amount(amount: float) -> FlowType | None:
    """Return the cash-flow type implied by a transaction amount."""
    if amount > 0:
        return "inflow"
    if amount < 0:
        return "outflow"
    return None


def transfer_direction_for_amount(amount: float) -> TransferDirection | None:
    """Return the monitoring direction implied by an internal transfer amount."""
    if amount > 0:
        return "in"
    if amount < 0:
        return "out"
    return None


def _generate_id(*parts: str) -> str:
    """Generate a short deterministic identifier from string parts."""
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:16]


def slugify(value: str) -> str:
    """Return a stable lowercase slug for user-visible labels."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "group"


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
    def transfer_direction(self) -> TransferDirection | None:
        if self.flow_type != "transfer":
            return None
        return transfer_direction_for_amount(self.amount)

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
    transfer_sign_scope: TransferSignScope = "any"
    transfer_group_strategy: TransferGroupStrategy = "none"
    transfer_group_label: str | None = None
    transfer_note: str | None = None

    def matches(self, description: str) -> bool:
        return self.pattern.lower() in description.lower()

    def applies_to_source(self, transaction: Transaction) -> bool:
        return self.import_source is None or self.import_source == transaction.stable_import_source

    def applies_to_transfer_direction(self, transaction: Transaction) -> bool:
        return self.rule_type != "transfer" or self.transfer_sign_scope == "any" or self.transfer_sign_scope == transfer_direction_for_amount(transaction.amount)

    @staticmethod
    def make_id(
        pattern: str,
        category: str,
        owner: str,
        rule_type: FlowType = "outflow",
        priority: int = 0,
        salt: str = "",
        import_source: str | None = None,
        transfer_sign_scope: TransferSignScope = "any",
        transfer_group_strategy: TransferGroupStrategy = "none",
        transfer_group_label: str | None = None,
    ) -> str:
        return _generate_id(pattern.lower(), category, owner, rule_type, str(priority), import_source or "", transfer_sign_scope, transfer_group_strategy, transfer_group_label or "", salt)


def transfer_group_id_for_rule(rule: Rule, transaction: Transaction) -> str | None:
    """Return the automatic transfer group ID a transfer rule assigns."""
    if rule.rule_type != "transfer" or rule.transfer_group_strategy == "none":
        return None
    label = slugify(rule.transfer_group_label or f"rule-{rule.id[:8]}")
    amount = f"{abs(transaction.amount):.2f}"
    if rule.transfer_group_strategy == "fixed":
        return label
    if rule.transfer_group_strategy == "same_day_amount":
        return f"{label}-{transaction.date.isoformat()}-{amount}-{transaction.currency}"
    if rule.transfer_group_strategy == "same_month_amount":
        return f"{label}-{transaction.date:%Y-%m}-{amount}-{transaction.currency}"
    return None


@dataclass(frozen=True)
class BudgetTarget:
    id: str
    name: str
    target_type: BudgetTargetType
    category: str | None
    owner: str | None
    currency: str
    monthly_amount: float
    active: bool = True
    notes: str | None = None

    @staticmethod
    def make_id(name: str, target_type: BudgetTargetType, currency: str, salt: str = "") -> str:
        return _generate_id("budget", name.lower(), target_type, currency, salt)


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
