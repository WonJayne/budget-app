"""Immutable application state and explicit update operations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Iterable

from .models import AppMetadata, CategoryStyle, FlowType, Rule, Transaction, flow_type_for_amount
from .rules import RuleEngine

DEFAULT_OWNERS = ("Flo", "Nina", "Shared")
DEFAULT_CURRENCY = "CHF"
DEFAULT_ACCOUNT = "manual"
DEFAULT_INFLOW_CATEGORIES = ("Bonus", "Gift", "Refund", "Reimbursement", "Salary")
DEFAULT_OUTFLOW_CATEGORIES = ("Childcare", "Eating out", "Groceries", "Holidays", "Insurance", "Investments", "Rent", "Subscriptions", "Transport")


@dataclass(frozen=True)
class OptionCatalog:
    owners: tuple[str, ...]
    inflow_categories: tuple[str, ...]
    outflow_categories: tuple[str, ...]
    currencies: tuple[str, ...]
    accounts: tuple[str, ...]


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

    def option_catalog(self) -> OptionCatalog:
        owners = set(DEFAULT_OWNERS)
        inflow_categories: set[str] = set(DEFAULT_INFLOW_CATEGORIES)
        outflow_categories: set[str] = set(DEFAULT_OUTFLOW_CATEGORIES)
        currencies = {DEFAULT_CURRENCY}
        accounts = {DEFAULT_ACCOUNT}

        for transaction in self.transactions:
            if transaction.owner:
                owners.add(transaction.owner)
            if transaction.category:
                if transaction.amount > 0:
                    inflow_categories.add(transaction.category)
                elif transaction.amount < 0:
                    outflow_categories.add(transaction.category)
            currencies.add(transaction.currency)
            accounts.add(transaction.account)

        for rule in self.rules:
            owners.add(rule.owner)
            if rule.rule_type == "inflow":
                inflow_categories.add(rule.category)
            else:
                outflow_categories.add(rule.category)

        for style in self.category_styles:
            if style.category:
                inflow_categories.add(style.category)
                outflow_categories.add(style.category)

        return OptionCatalog(
            owners=tuple(sorted(owners)),
            inflow_categories=tuple(sorted(inflow_categories)),
            outflow_categories=tuple(sorted(outflow_categories)),
            currencies=tuple(sorted(currencies)),
            accounts=tuple(sorted(accounts)),
        )

    def add_transactions(self, transactions: Iterable[Transaction]) -> "AppState":
        existing_ids = {transaction.id for transaction in self.transactions}
        added = [transaction for transaction in transactions if transaction.id not in existing_ids]
        if not added:
            return self
        merged = self.transactions + tuple(added)
        return replace(self, transactions=RuleEngine(self.rules).classify_many(merged))

    def add_manual_transaction(
        self,
        *,
        flow_type: FlowType,
        tx_date: date,
        description: str,
        amount: float,
        currency: str,
        account: str,
        category: str,
        owner: str,
    ) -> "AppState":
        signed_amount = abs(amount) if flow_type == "inflow" else -abs(amount)
        transaction = Transaction(
            id=Transaction.make_manual_id(tx_date, account, description, signed_amount, currency, str(len(self.transactions))),
            date=tx_date,
            account=account,
            description=description,
            amount=signed_amount,
            currency=currency,
            source_file=None,
            category=category,
            owner=owner,
            assignment_source="manual",
            source_kind="manual",
        )
        return self.add_transactions((transaction,))

    def update_manual_transaction(
        self,
        transaction_id: str,
        *,
        flow_type: FlowType,
        tx_date: date,
        description: str,
        amount: float,
        currency: str,
        account: str,
        category: str,
        owner: str,
    ) -> "AppState":
        signed_amount = abs(amount) if flow_type == "inflow" else -abs(amount)
        updated = tuple(
            replace(
                transaction,
                date=tx_date,
                description=description,
                amount=signed_amount,
                currency=currency,
                account=account,
                category=category,
                owner=owner,
                assignment_source="manual",
                source_kind="manual",
            )
            if transaction.id == transaction_id and transaction.source_kind == "manual"
            else transaction
            for transaction in self.transactions
        )
        return replace(self, transactions=updated).reapply_rules()

    def remove_manual_transaction(self, transaction_id: str) -> "AppState":
        return replace(
            self,
            transactions=tuple(
                transaction
                for transaction in self.transactions
                if not (transaction.id == transaction_id and transaction.source_kind == "manual")
            ),
        )

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
