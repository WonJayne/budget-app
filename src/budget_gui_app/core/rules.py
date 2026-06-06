"""Classification rule engine for the budget GUI application.

This module provides a minimalistic rule engine to assign categories
and owners to transactions based on substring matching.  Rules are
evaluated by priority (higher first) and then by the order in which
they were provided.  When a rule matches a transaction's description
its category and owner are applied.  Transactions that do not match
any rule remain unchanged.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, List, Tuple

from .models import Rule, Transaction


class RuleEngine:
    """Engine for applying classification rules to transactions."""

    def __init__(self, rules: Iterable[Rule]) -> None:
        # Sort rules by descending priority and stable insertion order
        self._rules: List[Rule] = sorted(list(rules), key=lambda r: (-r.priority))

    def classify(self, transaction: Transaction) -> Transaction:
        """Return a new transaction with category and owner applied.

        Args:
            transaction: Original transaction to classify.

        Returns:
            A new ``Transaction`` instance with updated ``category`` and
            ``owner`` if a rule matched.  If no rule matched the
            original transaction is returned unmodified.
        """
        for rule in self._rules:
            if rule.matches(transaction.description):
                # Only replace category/owner if not already set
                new_category = transaction.category or rule.category
                new_owner = transaction.owner or rule.owner
                return replace(transaction, category=new_category, owner=new_owner)
        return transaction

    def classify_many(self, transactions: Iterable[Transaction]) -> Tuple[Transaction, ...]:
        """Classify an iterable of transactions.

        Args:
            transactions: Iterable of transactions to classify.

        Returns:
            A tuple of classified transactions.  The input ordering is
            preserved.
        """
        return tuple(self.classify(tx) for tx in transactions)