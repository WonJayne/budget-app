"""Application state and update operations.

The ``AppState`` class represents the complete in‑memory state of the
budget application.  It holds all imported transactions, all
classification rules and styling information for categories.  State is
immutable: operations return new instances rather than modifying
existing ones.  This approach simplifies reasoning about updates and
facilitates persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Mapping, Optional, Tuple

from .models import CategoryStyle, Rule, Transaction


@dataclass(frozen=True)
class AppState:
    """Immutable container for the application’s state."""

    transactions: Tuple[Transaction, ...] = ()
    rules: Tuple[Rule, ...] = ()
    category_styles: Dict[str, CategoryStyle] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Ensure category_styles is a dict even if None passed
        if self.category_styles is None:
            object.__setattr__(self, "category_styles", {})

    @staticmethod
    def empty() -> "AppState":
        """Return a new, empty application state."""
        return AppState(transactions=(), rules=(), category_styles={})

    # Transaction operations
    def add_transactions(self, transactions: Iterable[Transaction]) -> "AppState":
        """Return a new state with the provided transactions added.

        Existing transactions are preserved.  Duplicate transactions
        (identified by matching ``Transaction.id``) are ignored.  The
        new transactions are appended in the order received.
        """
        existing_ids = {tx.id for tx in self.transactions}
        new_list = list(self.transactions)
        for tx in transactions:
            if tx.id not in existing_ids:
                new_list.append(tx)
                existing_ids.add(tx.id)
        return replace(self, transactions=tuple(new_list))

    def update_transaction(self, transaction_id: str, category: Optional[str], owner: Optional[str], ignored: Optional[bool] = None) -> "AppState":
        """Return a new state with an updated transaction.

        Args:
            transaction_id: Identifier of the transaction to update.
            category: New category value (``None`` to unset).
            owner: New owner value (``None`` to unset).
            ignored: Optional new ignored flag.  If ``None``, the
                existing ignored flag is preserved.

        Returns:
            A new state with the updated transaction.
        """
        updated = []
        found = False
        for tx in self.transactions:
            if tx.id == transaction_id:
                found = True
                new_ignored = tx.ignored if ignored is None else ignored
                updated.append(replace(tx, category=category, owner=owner, ignored=new_ignored))
            else:
                updated.append(tx)
        if not found:
            return self  # no change
        return replace(self, transactions=tuple(updated))

    # Rule operations
    def add_rule(self, rule: Rule) -> "AppState":
        """Return a new state with the rule appended."""
        return replace(self, rules=self.rules + (rule,))

    def remove_rule(self, rule_id: str) -> "AppState":
        """Return a new state with the specified rule removed."""
        filtered = tuple(r for r in self.rules if r.id != rule_id)
        return replace(self, rules=filtered)

    # Category style operations
    def set_category_colour(self, category: str, colour: Optional[str]) -> "AppState":
        """Return a new state with the colour assigned to the category."""
        styles = dict(self.category_styles)
        styles[category] = CategoryStyle(category=category, colour=colour)
        return replace(self, category_styles=styles)

    # Clearing
    def clear(self) -> "AppState":
        """Return a new, empty state."""
        return AppState.empty()