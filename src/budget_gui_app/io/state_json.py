"""JSON persistence for the application state.

This module provides utility functions to serialise and deserialise
``AppState`` instances to and from JSON files.  The JSON format is
kept simple and human‑readable.  Dates are stored as ISO strings.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from ..core.models import CategoryStyle, Rule, Transaction
from ..core.state import AppState


def save_state(state: AppState, path: Path) -> None:
    """Serialise the entire application state to a JSON file."""
    obj: Dict[str, Any] = {}
    # Transactions
    obj["transactions"] = [
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
            "ignored": tx.ignored,
        }
        for tx in state.transactions
    ]
    # Rules
    obj["rules"] = [
        {
            "id": r.id,
            "pattern": r.pattern,
            "category": r.category,
            "owner": r.owner,
            "priority": r.priority,
        }
        for r in state.rules
    ]
    # Category styles
    obj["category_styles"] = {
        cat: {"category": style.category, "colour": style.colour}
        for cat, style in state.category_styles.items()
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def load_state(path: Path) -> AppState:
    """Load application state from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    txs = []
    for item in obj.get("transactions", []):
        txs.append(
            Transaction(
                id=item["id"],
                date=datetime.fromisoformat(item["date"]).date(),
                account=item["account"],
                description=item["description"],
                amount=float(item["amount"]),
                currency=item["currency"],
                source_file=item.get("source_file"),
                category=item.get("category"),
                owner=item.get("owner"),
                ignored=bool(item.get("ignored", False)),
            )
        )
    rules = []
    for item in obj.get("rules", []):
        rules.append(
            Rule(
                id=item["id"],
                pattern=item["pattern"],
                category=item["category"],
                owner=item["owner"],
                priority=int(item.get("priority", 0)),
            )
        )
    styles = {}
    for cat, item in obj.get("category_styles", {}).items():
        styles[cat] = CategoryStyle(category=item["category"], colour=item.get("colour"))
    return AppState(transactions=tuple(txs), rules=tuple(rules), category_styles=styles)