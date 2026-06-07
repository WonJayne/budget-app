"""Rule-based transaction classification."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import Rule, Transaction


class RuleEngine:
    """Apply rules by priority, source specificity, and insertion order."""

    def __init__(self, rules: Iterable[Rule]) -> None:
        indexed = list(enumerate(rules))
        self._rules = [
            rule
            for _, rule in sorted(
                indexed,
                key=lambda item: (-item[1].priority, 0 if item[1].import_source is not None else 1, item[0]),
            )
        ]

    def classify(self, transaction: Transaction) -> Transaction:
        """Classify a transaction without overwriting manual assignments."""
        if transaction.assignment_source == "manual":
            return transaction

        base = transaction
        if transaction.assignment_source == "rule":
            base = replace(transaction, category=None, owner=None, assignment_source=None, cash_flow_type=None)

        implied_flow_type = base.flow_type
        if implied_flow_type is None:
            return base

        for rule in self._rules:
            compatible = rule.rule_type == "transfer" or rule.rule_type == implied_flow_type
            if compatible and rule.applies_to_source(base) and rule.applies_to_transfer_direction(base) and rule.matches(base.description):
                return replace(
                    base,
                    category=rule.category,
                    owner=rule.owner,
                    cash_flow_type=rule.rule_type,
                    assignment_source="rule",
                )
        return base

    def classify_many(self, transactions: Iterable[Transaction]) -> tuple[Transaction, ...]:
        return tuple(self.classify(transaction) for transaction in transactions)
