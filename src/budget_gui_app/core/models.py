"""Immutable core models for the budget application."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Literal

AssignmentSource = Literal["manual", "rule"] | None


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

    @staticmethod
    def make_id(date: date, account: str, description: str, amount: float, currency: str) -> str:
        """Derive a deterministic ID from raw transaction fields."""
        return _generate_id(date.isoformat(), account, description, f"{amount:.2f}", currency)


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    category: str
    owner: str
    priority: int = 0

    def matches(self, description: str) -> bool:
        return self.pattern.lower() in description.lower()

    @staticmethod
    def make_id(pattern: str, category: str, owner: str, priority: int = 0, salt: str = "") -> str:
        return _generate_id(pattern.lower(), category, owner, str(priority), salt)


@dataclass(frozen=True)
class CategoryStyle:
    category: str
    colour: str | None = None


@dataclass(frozen=True)
class AppMetadata:
    schema_version: int = 1
