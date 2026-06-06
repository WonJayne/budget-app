"""JSON import/export for complete application state and profile data."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from ..core.models import AppMetadata, AppProfile, CategoryStyle, Rule, Transaction
from ..core.state import AppState


class StateJsonRepository:
    def save(self, state: AppState, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(state), indent=2), encoding="utf-8")

    def load(self, path: Path) -> AppState:
        return self.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_profile(self, state: AppState, path: Path) -> None:
        path.write_text(json.dumps(self.to_profile_dict(state), indent=2), encoding="utf-8")

    def load_profile(self, state: AppState, path: Path) -> AppState:
        return self.apply_profile_dict(state, json.loads(path.read_text(encoding="utf-8")))

    def to_dict(self, state: AppState) -> dict[str, Any]:
        """Export a full backup JSON payload containing complete app state."""
        return {
            "metadata": self._metadata_to_dict(state.metadata),
            "profile": self._profile_to_dict(state.profile),
            "transactions": [self._transaction_to_dict(tx) for tx in state.transactions],
            "rules": [self._rule_to_dict(rule) for rule in state.rules],
            "category_styles": [self._category_style_to_dict(style) for style in state.category_styles],
        }

    def to_profile_dict(self, state: AppState) -> dict[str, Any]:
        """Export profile JSON without transaction ledger data."""
        catalog = state.option_catalog()
        return {
            "metadata": self._metadata_to_dict(state.metadata),
            "profile": {
                "owners": list(catalog.owners),
                "inflow_categories": list(catalog.inflow_categories),
                "outflow_categories": list(catalog.outflow_categories),
                "currencies": list(catalog.currencies),
                "accounts": list(catalog.accounts),
            },
            "rules": [self._rule_to_dict(rule) for rule in state.rules],
            "category_styles": [self._category_style_to_dict(style) for style in state.category_styles],
        }

    def from_dict(self, data: dict[str, Any]) -> AppState:
        metadata = self._metadata_from_dict(data.get("metadata", {}))
        return AppState(
            transactions=self._transactions_from_data(data),
            rules=self._rules_from_data(data),
            category_styles=self._category_styles_from_data(data),
            metadata=metadata,
            profile=self._profile_from_data(data),
        )

    def apply_profile_dict(self, state: AppState, data: dict[str, Any]) -> AppState:
        """Apply rules/profile JSON without touching existing transactions."""
        metadata = self._metadata_from_dict(data.get("metadata", {}))
        profile_state = replace(
            state,
            rules=self._rules_from_data(data),
            category_styles=self._category_styles_from_data(data),
            metadata=metadata,
            profile=self._profile_from_data(data),
        )
        return profile_state.reapply_rules()

    def _metadata_to_dict(self, metadata: AppMetadata) -> dict[str, Any]:
        return {"schema_version": metadata.schema_version}

    def _metadata_from_dict(self, data: dict[str, Any]) -> AppMetadata:
        return AppMetadata(schema_version=int(data.get("schema_version", 1)))

    def _profile_to_dict(self, profile: AppProfile) -> dict[str, list[str]]:
        return {
            "owners": list(profile.owners),
            "inflow_categories": list(profile.inflow_categories),
            "outflow_categories": list(profile.outflow_categories),
            "currencies": list(profile.currencies),
            "accounts": list(profile.accounts),
        }

    def _profile_from_data(self, data: dict[str, Any]) -> AppProfile:
        profile = data.get("profile", {})
        return AppProfile(
            owners=tuple(profile.get("owners", ())),
            inflow_categories=tuple(profile.get("inflow_categories", ())),
            outflow_categories=tuple(profile.get("outflow_categories", ())),
            currencies=tuple(profile.get("currencies", ())),
            accounts=tuple(profile.get("accounts", ())),
        )

    def _transaction_to_dict(self, tx: Transaction) -> dict[str, Any]:
        return {
            "id": tx.id,
            "date": tx.date.isoformat(),
            "account": tx.account,
            "description": tx.description,
            "amount": tx.amount,
            "currency": tx.currency,
            "source_file": tx.source_file,
            "category": tx.category,
            "owner": tx.owner,
            "assignment_source": tx.assignment_source,
            "ignored": tx.ignored,
            "source_kind": tx.source_kind,
            "entry_source": tx.entry_source,
            "edited": tx.edited,
        }

    def _rule_to_dict(self, rule: Rule) -> dict[str, Any]:
        return {
            "id": rule.id,
            "pattern": rule.pattern,
            "category": rule.category,
            "owner": rule.owner,
            "rule_type": rule.rule_type,
            "priority": rule.priority,
        }

    def _category_style_to_dict(self, style: CategoryStyle) -> dict[str, str | None]:
        return {"category": style.category, "colour": style.colour}

    def _source_defaults(self, item: dict[str, Any]) -> tuple[str, str]:
        entry_source = item.get("entry_source")
        if entry_source not in ("csv", "manual"):
            entry_source = "manual" if item.get("source_file") in (None, "manual") else "csv"
        source_kind = item.get("source_kind")
        if source_kind not in ("imported", "manual"):
            source_kind = "manual" if entry_source == "manual" else "imported"
        return source_kind, entry_source

    def _transactions_from_data(self, data: dict[str, Any]) -> tuple[Transaction, ...]:
        transactions: list[Transaction] = []
        for item in data.get("transactions", []):
            source_kind, entry_source = self._source_defaults(item)
            transactions.append(
                Transaction(
                    id=item["id"],
                    date=date.fromisoformat(item["date"]),
                    account=item["account"],
                    description=item["description"],
                    amount=float(item["amount"]),
                    currency=item["currency"],
                    source_file=item.get("source_file"),
                    category=item.get("category"),
                    owner=item.get("owner"),
                    assignment_source=item.get("assignment_source"),
                    ignored=bool(item.get("ignored", False)),
                    source_kind=source_kind,
                    entry_source=entry_source,
                    edited=bool(item.get("edited", False)),
                )
            )
        return tuple(transactions)

    def _rules_from_data(self, data: dict[str, Any]) -> tuple[Rule, ...]:
        return tuple(
            Rule(
                id=item["id"],
                pattern=item["pattern"],
                category=item["category"],
                owner=item["owner"],
                rule_type=item.get("rule_type", "outflow"),
                priority=int(item.get("priority", 0)),
            )
            for item in data.get("rules", [])
        )

    def _category_styles_from_data(self, data: dict[str, Any]) -> tuple[CategoryStyle, ...]:
        style_items = data.get("category_styles", [])
        if isinstance(style_items, dict):
            style_items = style_items.values()
        return tuple(CategoryStyle(category=item["category"], colour=item.get("colour")) for item in style_items)


def save_state(state: AppState, path: Path) -> None:
    StateJsonRepository().save(state, path)


def load_state(path: Path) -> AppState:
    return StateJsonRepository().load(path)
