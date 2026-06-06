"""Immutable core models for the budget application."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Literal

AssignmentSource = Literal["manual", "rule"] | None
FlowType = Literal["inflow", "outflow"]
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


@dataclass(frozen=True)
class Transaction:
    id: str
    date: date
    account: str
    description: str
    amount: float
    currency: str
    source_file: str | None = None
    category: str | None = None
    owner: str | None = None
    assignment_source: AssignmentSource = None
    ignored: bool = False
    source_kind: SourceKind = "imported"
    entry_source: EntrySource = "csv"
    edited: bool = False

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
        return flow_type_for_amount(self.amount)


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    category: str
    owner: str
    rule_type: FlowType = "outflow"
    priority: int = 0

    def matches(self, description: str) -> bool:
        return self.pattern.lower() in description.lower()

    @staticmethod
    def make_id(pattern: str, category: str, owner: str, rule_type: FlowType = "outflow", priority: int = 0, salt: str = "") -> str:
        return _generate_id(pattern.lower(), category, owner, rule_type, str(priority), salt)


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
