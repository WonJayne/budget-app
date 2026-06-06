"""Immutable application state and explicit update operations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from .models import AppMetadata, CategoryStyle, Rule, Transaction
from .rules import RuleEngine


@dataclass(frozen=True)
class AppState:
    transactions: tuple[Transaction, ...] = ()
    rules: tuple[Rule, ...] = ()
    category_styles: tuple[CategoryStyle, ...] = ()
    metadata: AppMetadata = AppMetadata()

    @staticmethod
    def empty() -> "AppState":
        return AppState()

    def category_style_map(self) -> dict[str, CategoryStyle]:
        return {style.category: style for style in self.category_styles}

    def add_transactions(self, transactions: Iterable[Transaction]) -> "AppState":
        existing_ids = {transaction.id for transaction in self.transactions}
        added = [transaction for transaction in transactions if transaction.id not in existing_ids]
        if not added:
            return self
        merged = self.transactions + tuple(added)
        return replace(self, transactions=RuleEngine(self.rules).classify_many(merged))

    def add_rule(self, rule: Rule) -> "AppState":
        return replace(self, rules=self.rules + (rule,)).reapply_rules()

    def update_rule(self, rule: Rule) -> "AppState":
        return replace(self, rules=tuple(rule if existing.id == rule.id else existing for existing in self.rules)).reapply_rules()

    def remove_rule(self, rule_id: str) -> "AppState":
        return replace(self, rules=tuple(rule for rule in self.rules if rule.id != rule_id)).reapply_rules()

    def manually_assign_transaction(self, transaction_id: str, category: str, owner: str) -> "AppState":
        updated = tuple(
            replace(transaction, category=category, owner=owner, assignment_source="manual")
            if transaction.id == transaction_id
            else transaction
            for transaction in self.transactions
        )
        return replace(self, transactions=updated)

    def ignore_transaction(self, transaction_id: str, ignored: bool = True) -> "AppState":
        updated = tuple(
            replace(transaction, ignored=ignored) if transaction.id == transaction_id else transaction
            for transaction in self.transactions
        )
        return replace(self, transactions=updated)

    def set_category_colour(self, category: str, colour: str | None) -> "AppState":
        styles = self.category_style_map()
        styles[category] = CategoryStyle(category=category, colour=colour or None)
        return replace(self, category_styles=tuple(styles[cat] for cat in sorted(styles)))

    def clear(self) -> "AppState":
        return AppState(metadata=self.metadata)

    def reapply_rules(self) -> "AppState":
        return replace(self, transactions=RuleEngine(self.rules).classify_many(self.transactions))
