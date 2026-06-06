"""JSON import/export for complete application state."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ..core.models import AppMetadata, CategoryStyle, Rule, Transaction
from ..core.state import AppState


class StateJsonRepository:
    def save(self, state: AppState, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(state), indent=2), encoding="utf-8")

    def load(self, path: Path) -> AppState:
        return self.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def to_dict(self, state: AppState) -> dict[str, Any]:
        return {
            "metadata": {"schema_version": state.metadata.schema_version},
            "transactions": [
                {
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
                for tx in state.transactions
            ],
            "rules": [
                {
                    "id": rule.id,
                    "pattern": rule.pattern,
                    "category": rule.category,
                    "owner": rule.owner,
                    "rule_type": rule.rule_type,
                    "priority": rule.priority,
                }
                for rule in state.rules
            ],
            "category_styles": [
                {"category": style.category, "colour": style.colour} for style in state.category_styles
            ],
        }

    def from_dict(self, data: dict[str, Any]) -> AppState:
        metadata_data = data.get("metadata", {})
        def source_defaults(item: dict[str, Any]) -> tuple[str, str]:
            entry_source = item.get("entry_source")
            if entry_source not in ("csv", "manual"):
                entry_source = "manual" if item.get("source_file") in (None, "manual") else "csv"
            source_kind = item.get("source_kind")
            if source_kind not in ("imported", "manual"):
                source_kind = "manual" if entry_source == "manual" else "imported"
            return source_kind, entry_source

        transactions = tuple(
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
                source_kind=source_defaults(item)[0],
                entry_source=source_defaults(item)[1],
                edited=bool(item.get("edited", False)),
            )
            for item in data.get("transactions", [])
        )
        rules = tuple(
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
        style_items = data.get("category_styles", [])
        if isinstance(style_items, dict):
            style_items = style_items.values()
        styles = tuple(CategoryStyle(category=item["category"], colour=item.get("colour")) for item in style_items)
        return AppState(
            transactions=transactions,
            rules=rules,
            category_styles=styles,
            metadata=AppMetadata(schema_version=int(metadata_data.get("schema_version", 1))),
        )


def save_state(state: AppState, path: Path) -> None:
    StateJsonRepository().save(state, path)


def load_state(path: Path) -> AppState:
    return StateJsonRepository().load(path)
