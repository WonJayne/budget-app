"""NiceGUI data, rules, and review page."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from nicegui import events, ui

from ..core.importers import TransactionImporter
from ..core.models import Rule
from ..core.state import AppState
from ..io.state_json import StateJsonRepository


@dataclass
class UiState:
    state: AppState
    refresh: Callable[[], None]


def suggested_pattern(description: str) -> str:
    words = [word.strip(" ,.;:-_/()[]").lower() for word in description.split()]
    return next((word for word in words if word), description.lower())


def build_data_page(holder: UiState) -> None:
    importer = TransactionImporter()
    repository = StateJsonRepository()

    def set_state(state: AppState) -> None:
        holder.state = state
        holder.refresh()

    async def import_csv(event: events.UploadEventArguments) -> None:
        suffix = Path(event.name).suffix or ".csv"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = event.content.read()
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        try:
            transactions = importer.import_csv(temp_path)
            existing_ids = {transaction.id for transaction in holder.state.transactions}
            new_count = sum(1 for transaction in transactions if transaction.id not in existing_ids)
            skipped_count = len(transactions) - new_count
            set_state(holder.state.add_transactions(transactions))
            ui.notify(f"Imported {new_count} new transactions, skipped {skipped_count} duplicates.")
        finally:
            temp_path.unlink(missing_ok=True)

    async def import_state(event: events.UploadEventArguments) -> None:
        data = event.content.read().decode("utf-8")
        set_state(repository.from_dict(json.loads(data)))
        ui.notify("State imported.")

    def export_state() -> None:
        data = json.dumps(repository.to_dict(holder.state), indent=2).encode("utf-8")
        ui.download(data, filename="budget_state.json")

    def clear_state() -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Clear all transactions, rules, and category colours?")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Clear", color="negative", on_click=lambda: (set_state(holder.state.clear()), dialog.close(), ui.notify("State cleared.")))
        dialog.open()

    def save_rule(rule_id: str | None, pattern_input, category_input, owner_input, priority_input, dialog) -> None:
        priority = int(priority_input.value or 0)
        rule = Rule(
            id=rule_id or Rule.make_id(pattern_input.value, category_input.value, owner_input.value, priority, str(len(holder.state.rules))),
            pattern=pattern_input.value,
            category=category_input.value,
            owner=owner_input.value,
            priority=priority,
        )
        set_state(holder.state.update_rule(rule) if rule_id else holder.state.add_rule(rule))
        dialog.close()
        ui.notify("Rule saved.")

    def rule_dialog(rule: Rule | None = None) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Edit rule" if rule else "Add rule").classes("text-lg font-bold")
            pattern = ui.input("Pattern", value=rule.pattern if rule else "").props("autofocus").classes("w-full")
            category = ui.input("Category", value=rule.category if rule else "").classes("w-full")
            owner = ui.input("Owner", value=rule.owner if rule else "").classes("w-full")
            priority = ui.number("Priority", value=rule.priority if rule else 0, format="%.0f").classes("w-full")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Save", on_click=lambda: save_rule(rule.id if rule else None, pattern, category, owner, priority, dialog))
        dialog.open()

    def assign_dialog(transaction_id: str) -> None:
        transaction = next(tx for tx in holder.state.transactions if tx.id == transaction_id)
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(transaction.description).classes("font-bold")
            category = ui.input("Category", value=transaction.category or "").classes("w-full")
            owner = ui.input("Owner", value=transaction.owner or "").classes("w-full")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Assign", on_click=lambda: (set_state(holder.state.manually_assign_transaction(transaction.id, category.value, owner.value)), dialog.close(), ui.notify("Transaction assigned.")))
        dialog.open()

    def create_rule_dialog(transaction_id: str) -> None:
        transaction = next(tx for tx in holder.state.transactions if tx.id == transaction_id)
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(transaction.description).classes("font-bold")
            pattern = ui.input("Pattern", value=suggested_pattern(transaction.description)).classes("w-full")
            category = ui.input("Category", value=transaction.category or "").classes("w-full")
            owner = ui.input("Owner", value=transaction.owner or "shared").classes("w-full")
            priority = ui.number("Priority", value=0, format="%.0f").classes("w-full")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Save rule", on_click=lambda: save_rule(None, pattern, category, owner, priority, dialog))
        dialog.open()

    @ui.refreshable
    def content() -> None:
        with ui.column().classes("w-full gap-4"):
            with ui.row().classes("items-center"):
                ui.upload(label="Import CSV", auto_upload=True, multiple=True, on_upload=import_csv).props("accept=.csv").classes("max-w-sm")
                ui.upload(label="Import state", auto_upload=True, on_upload=import_state).props("accept=.json").classes("max-w-sm")
                ui.button("Export state", on_click=export_state)
                ui.button("Clear all data", color="negative", on_click=clear_state)

            ui.label("Rules").classes("text-xl font-bold")
            with ui.row():
                ui.button("Add rule", on_click=lambda: rule_dialog())
            columns = [
                {"name": "pattern", "label": "Pattern", "field": "pattern", "align": "left"},
                {"name": "category", "label": "Category", "field": "category", "align": "left"},
                {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
                {"name": "priority", "label": "Priority", "field": "priority"},
                {"name": "actions", "label": "Actions", "field": "actions"},
            ]
            rows = [{"id": rule.id, "pattern": rule.pattern, "category": rule.category, "owner": rule.owner, "priority": rule.priority, "actions": ""} for rule in holder.state.rules]
            table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
            table.add_slot("body-cell-actions", """
                <q-td :props="props">
                  <q-btn dense flat color="primary" label="Edit" @click="$parent.$emit('edit', props.row.id)" />
                  <q-btn dense flat color="negative" label="Delete" @click="$parent.$emit('delete', props.row.id)" />
                </q-td>
            """)
            table.on("edit", lambda event: rule_dialog(next(rule for rule in holder.state.rules if rule.id == event.args)))
            table.on("delete", lambda event: (set_state(holder.state.remove_rule(event.args)), ui.notify("Rule deleted.")))

            ui.label("Review unclassified transactions").classes("text-xl font-bold")
            review_rows = [tx for tx in holder.state.transactions if (tx.category is None or tx.owner is None) and not tx.ignored]
            if not review_rows:
                ui.label("No unclassified transactions.").classes("text-gray-500")
            for tx in review_rows:
                with ui.card().classes("w-full"):
                    with ui.row().classes("items-center w-full"):
                        ui.label(tx.date.isoformat()).classes("w-24")
                        ui.label(tx.account).classes("w-32")
                        ui.label(tx.description).classes("grow")
                        ui.label(f"{tx.amount:.2f} {tx.currency}").classes("w-32 text-right")
                        ui.button("Assign", on_click=lambda _, tx_id=tx.id: assign_dialog(tx_id))
                        ui.button("Create rule", on_click=lambda _, tx_id=tx.id: create_rule_dialog(tx_id))
                        ui.button("Ignore", color="warning", on_click=lambda _, tx_id=tx.id: (set_state(holder.state.ignore_transaction(tx_id)), ui.notify("Transaction ignored.")))

    content()
    holder.refresh = content.refresh
