"""Immutable application state and explicit update operations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Iterable

from .models import AppMetadata, AppProfile, BudgetTarget, CategoryStyle, FlowType, Rule, Transaction
from .rules import RuleEngine
from .sankey import is_valid_hex_colour

DEFAULT_OWNERS = ("Flo", "Nina", "Shared")
DEFAULT_CURRENCY = "CHF"
DEFAULT_ACCOUNT = "manual"
DEFAULT_INFLOW_CATEGORIES = ("Bonus", "Gift", "Refund", "Reimbursement", "Salary")
DEFAULT_OUTFLOW_CATEGORIES = ("Childcare", "Eating out", "Groceries", "Holidays", "Insurance", "Investments", "Rent", "Subscriptions", "Transport")
DEFAULT_TRANSFER_CATEGORIES = ("Internal transfer", "Credit card settlement", "Savings transfer")


@dataclass(frozen=True)
class OptionCatalog:
    owners: tuple[str, ...]
    inflow_categories: tuple[str, ...]
    outflow_categories: tuple[str, ...]
    currencies: tuple[str, ...]
    accounts: tuple[str, ...]
    import_sources: tuple[str, ...]


@dataclass(frozen=True)
class AppState:
    transactions: tuple[Transaction, ...] = ()
    rules: tuple[Rule, ...] = ()
    category_styles: tuple[CategoryStyle, ...] = ()
    budget_targets: tuple[BudgetTarget, ...] = ()
    metadata: AppMetadata = AppMetadata()
    profile: AppProfile = AppProfile()

    @staticmethod
    def empty() -> "AppState":
        return AppState()

    def category_style_map(self) -> dict[str, CategoryStyle]:
        return {style.category: style for style in self.category_styles}

    def option_catalog(self) -> OptionCatalog:
        owners = set(DEFAULT_OWNERS) | set(self.profile.owners)
        inflow_categories: set[str] = set(DEFAULT_INFLOW_CATEGORIES) | set(self.profile.inflow_categories)
        outflow_categories: set[str] = set(DEFAULT_OUTFLOW_CATEGORIES) | set(self.profile.outflow_categories)
        currencies = {DEFAULT_CURRENCY} | set(self.profile.currencies)
        accounts = {DEFAULT_ACCOUNT} | set(self.profile.accounts)
        import_sources = {"Manual"}

        for transaction in self.transactions:
            if transaction.owner:
                owners.add(transaction.owner)
            if transaction.category:
                if transaction.flow_type == "inflow":
                    inflow_categories.add(transaction.category)
                elif transaction.flow_type == "outflow":
                    outflow_categories.add(transaction.category)
                elif transaction.flow_type == "transfer":
                    outflow_categories.add(transaction.category)
            currencies.add(transaction.currency)
            accounts.add(transaction.account)
            if transaction.stable_import_source:
                import_sources.add(transaction.stable_import_source)

        for rule in self.rules:
            owners.add(rule.owner)
            if rule.rule_type == "inflow":
                inflow_categories.add(rule.category)
            elif rule.rule_type == "outflow":
                outflow_categories.add(rule.category)
            else:
                outflow_categories.add(rule.category)
            if rule.import_source:
                import_sources.add(rule.import_source)

        for target in self.budget_targets:
            if target.owner:
                owners.add(target.owner)
            if target.category:
                if target.target_type == "inflow":
                    inflow_categories.add(target.category)
                elif target.target_type == "outflow":
                    outflow_categories.add(target.category)
            currencies.add(target.currency)

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
            import_sources=tuple(sorted(import_sources)),
        )

    def import_transactions_append(self, transactions: Iterable[Transaction]) -> tuple["AppState", dict[str, int]]:
        rows = tuple(transactions)
        existing_ids = {transaction.id for transaction in self.transactions}
        new_rows = tuple(transaction for transaction in rows if transaction.id not in existing_ids)
        report = {"added": len(new_rows), "skipped": len(rows) - len(new_rows), "replaced": 0, "missing": 0}
        return (self.add_transactions(new_rows) if new_rows else self, report)

    def import_transactions_replace_source_period(self, transactions: Iterable[Transaction], import_source: str) -> tuple["AppState", dict[str, int]]:
        rows = tuple(transactions)
        if not rows:
            return self, {"added": 0, "skipped": 0, "replaced": 0, "missing": 0}
        start = min(transaction.date for transaction in rows)
        end = max(transaction.date for transaction in rows)
        kept = tuple(
            transaction
            for transaction in self.transactions
            if not (
                transaction.entry_source == "csv"
                and transaction.stable_import_source == import_source
                and start <= transaction.date <= end
            )
        )
        replaced = len(self.transactions) - len(kept)
        merged = kept + rows
        report = {"added": len(rows), "skipped": 0, "replaced": replaced, "missing": replaced}
        return replace(self, transactions=RuleEngine(self.rules).classify_many(merged)), report

    def reconcile_transactions_source_period(self, transactions: Iterable[Transaction], import_source: str) -> dict[str, int]:
        rows = tuple(transactions)
        if not rows:
            return {"added": 0, "skipped": 0, "replaced": 0, "missing": 0}
        start = min(transaction.date for transaction in rows)
        end = max(transaction.date for transaction in rows)
        incoming_ids = {transaction.id for transaction in rows}
        existing_period_ids = {
            transaction.id
            for transaction in self.transactions
            if transaction.entry_source == "csv" and transaction.stable_import_source == import_source and start <= transaction.date <= end
        }
        return {
            "added": len(incoming_ids - existing_period_ids),
            "skipped": len(incoming_ids & existing_period_ids),
            "replaced": 0,
            "missing": len(existing_period_ids - incoming_ids),
        }

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
        transfer_group_id: str | None = None,
        transfer_note: str | None = None,
    ) -> "AppState":
        signed_amount = amount if flow_type == "transfer" else abs(amount) if flow_type == "inflow" else -abs(amount)
        transaction = Transaction(
            id=Transaction.make_manual_id(tx_date, account, description, signed_amount, currency, str(len(self.transactions))),
            date=tx_date,
            account=account,
            description=description,
            amount=signed_amount,
            currency=currency,
            source_file=None,
            import_source="Manual",
            cash_flow_type=flow_type,
            category=category,
            owner=owner,
            assignment_source="manual",
            source_kind="manual",
            entry_source="manual",
            transfer_group_id=transfer_group_id if flow_type == "transfer" else None,
            transfer_note=transfer_note if flow_type == "transfer" else None,
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
        transfer_group_id: str | None = None,
        transfer_note: str | None = None,
    ) -> "AppState":
        signed_amount = amount if flow_type == "transfer" else abs(amount) if flow_type == "inflow" else -abs(amount)
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
                cash_flow_type=flow_type,
                import_source="Manual",
                assignment_source="manual",
                source_kind="manual",
                entry_source="manual",
                edited=True,
                transfer_group_id=transfer_group_id if flow_type == "transfer" else None,
                transfer_note=transfer_note if flow_type == "transfer" else None,
            )
            if transaction.id == transaction_id and transaction.source_kind == "manual"
            else transaction
            for transaction in self.transactions
        )
        return replace(self, transactions=updated).reapply_rules()

    def update_transaction(
        self,
        transaction_id: str,
        *,
        flow_type: FlowType,
        tx_date: date,
        description: str,
        amount: float,
        currency: str,
        account: str,
        category: str | None,
        owner: str | None,
        ignored: bool,
        transfer_group_id: str | None = None,
        transfer_note: str | None = None,
    ) -> "AppState":
        """Update any transaction while preserving its stable transaction ID."""
        signed_amount = amount if flow_type == "transfer" else abs(amount) if flow_type == "inflow" else -abs(amount)
        category_value = category or None
        owner_value = owner or None
        updated = tuple(
            replace(
                transaction,
                date=tx_date,
                description=description,
                amount=signed_amount,
                currency=currency,
                account=account,
                category=category_value,
                owner=owner_value,
                cash_flow_type=flow_type,
                assignment_source="manual" if category_value or owner_value or flow_type == "transfer" else None,
                ignored=ignored,
                edited=True,
                transfer_group_id=transfer_group_id if flow_type == "transfer" else None,
                transfer_note=transfer_note if flow_type == "transfer" else None,
            )
            if transaction.id == transaction_id
            else transaction
            for transaction in self.transactions
        )
        return replace(self, transactions=updated).reapply_rules()

    def delete_transaction(self, transaction_id: str) -> "AppState":
        """Delete any transaction from state."""
        return replace(self, transactions=tuple(transaction for transaction in self.transactions if transaction.id != transaction_id))

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

    def manually_assign_transaction(self, transaction_id: str, category: str, owner: str, flow_type: FlowType | None = None) -> "AppState":
        updated = tuple(
            replace(transaction, category=category, owner=owner, cash_flow_type=flow_type or transaction.flow_type, assignment_source="manual")
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
        if colour:
            if not is_valid_hex_colour(colour):
                return self
            styles[category] = CategoryStyle(category=category, colour=colour)
        else:
            styles.pop(category, None)
        return replace(self, category_styles=tuple(styles[cat] for cat in sorted(styles)))

    def add_budget_target(self, target: BudgetTarget) -> "AppState":
        return replace(self, budget_targets=self.budget_targets + (target,))

    def update_budget_target(self, target: BudgetTarget) -> "AppState":
        return replace(self, budget_targets=tuple(target if existing.id == target.id else existing for existing in self.budget_targets))

    def remove_budget_target(self, target_id: str) -> "AppState":
        return replace(self, budget_targets=tuple(target for target in self.budget_targets if target.id != target_id))

    def clear_transactions(self) -> "AppState":
        """Remove ledger/manual entries while keeping rules, colours, and metadata."""
        return replace(self, transactions=())

    def clear_all_data(self) -> "AppState":
        """Reset transactions, rules, colours, and metadata to a fresh local state."""
        return AppState.empty()

    def clear(self) -> "AppState":
        return self.clear_all_data()

    def reapply_rules(self) -> "AppState":
        return replace(self, transactions=RuleEngine(self.rules).classify_many(self.transactions))
