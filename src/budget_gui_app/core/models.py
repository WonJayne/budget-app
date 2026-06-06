"""Data models for the budget GUI application.

This module defines immutable data classes for representing
transactions, classification rules and category styling.  Each model
uses ``@dataclass(frozen=True)`` to encourage immutability and make
state updates explicit.  Type hints are provided throughout for
static analysis and readability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


def _generate_id(*parts: str) -> str:
    """Generate a deterministic identifier from the provided string parts.

    The parts are concatenated with a null separator before hashing
    using SHA256.  The resulting hex digest is truncated for brevity.

    Args:
        *parts: Arbitrary strings contributing to the identifier.

    Returns:
        A 16‑character hexadecimal string.
    """
    joined = "\0".join(parts).encode("utf-8")
    digest = hashlib.sha256(joined).hexdigest()
    return digest[:16]


@dataclass(frozen=True)
class Transaction:
    """Immutable representation of a single transaction.

    Attributes:
        id: Unique identifier for the transaction.  Should be
            generated deterministically from the core fields.
        date: The posting date of the transaction.
        account: Logical account or source of the transaction.
        description: Free‑form description or merchant name.
        amount: Signed amount of the transaction.  Negative values
            represent expenses; positive values represent income.
        currency: ISO currency code (e.g. ``"CHF"``).
        source_file: Optional source filename from which the
            transaction was imported.  Useful for debugging and
            preventing duplicate imports.
        category: Optional assigned category.
        owner: Optional assigned owner (e.g. ``"shared"`` or an
            individual’s name).
        ignored: Whether this transaction should be excluded from
            visualisations.
    """

    id: str
    date: date
    account: str
    description: str
    amount: float
    currency: str
    source_file: Optional[str] = None
    category: Optional[str] = None
    owner: Optional[str] = None
    ignored: bool = False

    @staticmethod
    def make_id(date: date, account: str, description: str, amount: float, currency: str) -> str:
        """Derive a transaction identifier from its defining fields."""
        return _generate_id(date.isoformat(), account, description, f"{amount}", currency)


@dataclass(frozen=True)
class Rule:
    """Immutable classification rule.

    A rule matches transactions whose lower‑cased description contains
    the ``pattern`` substring.  When a rule matches it assigns the
    associated ``category`` and ``owner``.  Rules are evaluated by
    priority (descending) and then insertion order.
    """

    id: str
    pattern: str
    category: str
    owner: str
    priority: int = 0

    def matches(self, description: str) -> bool:
        """Return ``True`` if the rule matches the provided description."""
        return self.pattern.lower() in description.lower()


@dataclass(frozen=True)
class CategoryStyle:
    """Styling information for a category in the Sankey diagram."""

    category: str
    colour: Optional[str] = None