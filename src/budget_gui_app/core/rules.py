"""Rule-based transaction classification."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import Rule, Transaction, flow_type_for_amount


class RuleEngine:
    """Apply rules by descending priority while preserving insertion order."""

    def __init__(self, rules: Iterable[Rule]) -> None:
        indexed = list(enumerate(rules))
        self._rules = [rule for _, rule in sorted(indexed, key=lambda item: (-item[1].priority, item[0]))]

    def classify(self, transaction: Transaction) -> Transaction:
        """Classify a transaction without overwriting manual assignments."""
        if transaction.assignment_source == "manual":
            return transaction

        base = transaction
        if transaction.assignment_source == "rule":
            base = replace(transaction, category=None, owner=None, assignment_source=None)

        flow_type = flow_type_for_amount(base.amount)
        if flow_type is None:
            return base

        for rule in self._rules:
            if rule.rule_type == flow_type and rule.matches(base.description):
                return replace(base, category=rule.category, owner=rule.owner, assignment_source="rule")
        return base

    def classify_many(self, transactions: Iterable[Transaction]) -> tuple[Transaction, ...]:
        return tuple(self.classify(transaction) for transaction in transactions)
