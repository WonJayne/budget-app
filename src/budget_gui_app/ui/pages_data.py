"""NiceGUI data, rules, and review page."""

from __future__ import annotations

import inspect
import json
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from nicegui import events, ui

from ..core.importers import TransactionImporter
from ..core.models import FlowType, Rule, Transaction, flow_type_for_amount
from ..core.periods import PeriodFilter, available_years, default_period_filter
from ..core.state import AppState, DEFAULT_ACCOUNT, DEFAULT_CURRENCY
from ..io.state_json import StateJsonRepository
from ..io.transactions_csv import transactions_to_csv

OTHER_OPTION = "Other / new..."


@dataclass
class UiState:
    state: AppState
    refresh: Callable[[], None]


def upload_event_name(event: events.UploadEventArguments) -> str:
    file = getattr(event, "file", None)
    return getattr(file, "name", getattr(event, "name", "upload"))


async def upload_event_bytes(event: events.UploadEventArguments) -> bytes:
    file = getattr(event, "file", None)
    if file is not None:
        content = file.read()
        return await content if inspect.isawaitable(content) else content

    content = event.content.read()
    return await content if inspect.isawaitable(content) else content


async def upload_event_text(event: events.UploadEventArguments, encoding: str = "utf-8") -> str:
    file = getattr(event, "file", None)
    if file is not None:
        if hasattr(file, "text"):
            content = file.text(encoding)
            return await content if inspect.isawaitable(content) else content
        return (await upload_event_bytes(event)).decode(encoding)

    return (await upload_event_bytes(event)).decode(encoding)


def suggested_pattern(description: str) -> str:
    words = [word.strip(" ,.;:-_/()[]").lower() for word in description.split()]
    return next((word for word in words if word), description.lower())


def flow_label(amount: float) -> str:
    return flow_type_for_amount(amount) or "none"


def select_or_new(label: str, options: tuple[str, ...] | list[str], value: str | None = None):
    choices = list(dict.fromkeys([option for option in options if option]))
    initial = value if value in choices else (choices[0] if choices else OTHER_OPTION)
    if value and value not in choices:
        initial = OTHER_OPTION
    select = ui.select(choices + [OTHER_OPTION], label=label, value=initial).classes("w-full")
    new_value = ui.input(f"New {label.lower()}", value=value if value and value not in choices else "").classes("w-full")
    new_value.visible = initial == OTHER_OPTION
    select.on_value_change(lambda event: new_value.set_visibility(event.value == OTHER_OPTION))
    return select, new_value


def selected_value(select, new_value) -> str:
    return (new_value.value if select.value == OTHER_OPTION else select.value) or ""


@dataclass
class DataFilters:
    period: PeriodFilter | None = None


def build_data_page(holder: UiState) -> None:
    importer = TransactionImporter()
    repository = StateJsonRepository()
    filters = DataFilters()

    def set_state(state: AppState) -> None:
        holder.state = state
        holder.refresh()

    async def import_csv(event: events.UploadEventArguments) -> None:
        suffix = Path(upload_event_name(event)).suffix or ".csv"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await upload_event_bytes(event)
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
        data = await upload_event_text(event)
        set_state(repository.from_dict(json.loads(data)))
        ui.notify("State imported.")

    def export_state() -> None:
        data = json.dumps(repository.to_dict(holder.state), indent=2).encode("utf-8")
        ui.download(data, filename="budget_state.json")

    def export_csv() -> None:
        ui.download(transactions_to_csv(holder.state.transactions).encode("utf-8"), filename="budget_transactions_merged.csv")

    def clear_state() -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Clear all transactions, rules, and category colours?")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Clear", color="negative", on_click=lambda: (set_state(holder.state.clear()), dialog.close(), ui.notify("State cleared.")))
        dialog.open()

    def category_options(rule_type: FlowType) -> tuple[str, ...]:
        catalog = holder.state.option_catalog()
        return catalog.inflow_categories if rule_type == "inflow" else catalog.outflow_categories

    def save_rule(rule_id: str | None, pattern_input, rule_type_input, category_select, category_new, owner_select, owner_new, priority_input, dialog) -> None:
        priority = int(priority_input.value or 0)
        rule_type: FlowType = rule_type_input.value
        category = selected_value(category_select, category_new)
        owner = selected_value(owner_select, owner_new)
        rule = Rule(
            id=rule_id or Rule.make_id(pattern_input.value, category, owner, rule_type, priority, str(len(holder.state.rules))),
            pattern=pattern_input.value,
            category=category,
            owner=owner,
            rule_type=rule_type,
            priority=priority,
        )
        set_state(holder.state.update_rule(rule) if rule_id else holder.state.add_rule(rule))
        dialog.close()
        ui.notify("Rule saved.")

    def rule_dialog(rule: Rule | None = None, default_rule_type: FlowType = "outflow") -> None:
        catalog = holder.state.option_catalog()
        initial_type = rule.rule_type if rule else default_rule_type
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Edit rule" if rule else f"Add {initial_type} rule").classes("text-lg font-bold")
            pattern = ui.input("Pattern", value=rule.pattern if rule else "").props("autofocus").classes("w-full")
            rule_type = ui.select(["inflow", "outflow"], label="Rule type", value=initial_type).classes("w-full")
            category_select, category_new = select_or_new("Category", category_options(initial_type), rule.category if rule else None)

            def update_rule_category_options(event) -> None:
                category_select.set_options(list(category_options(event.value)) + [OTHER_OPTION])

            rule_type.on_value_change(update_rule_category_options)
            owner_select, owner_new = select_or_new("Owner", catalog.owners, rule.owner if rule else None)
            priority = ui.number("Priority", value=rule.priority if rule else 0, format="%.0f").classes("w-full")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Save", on_click=lambda: save_rule(rule.id if rule else None, pattern, rule_type, category_select, category_new, owner_select, owner_new, priority, dialog))
        dialog.open()

    def assign_dialog(transaction_id: str) -> None:
        transaction = next(tx for tx in holder.state.transactions if tx.id == transaction_id)
        tx_flow = flow_type_for_amount(transaction.amount) or "outflow"
        catalog = holder.state.option_catalog()
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(f"{tx_flow}: {transaction.description}").classes("font-bold")
            category_select, category_new = select_or_new("Category", category_options(tx_flow), transaction.category)
            owner_select, owner_new = select_or_new("Owner", catalog.owners, transaction.owner)
            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Assign", on_click=lambda: (set_state(holder.state.manually_assign_transaction(transaction.id, selected_value(category_select, category_new), selected_value(owner_select, owner_new))), dialog.close(), ui.notify("Transaction assigned.")))
        dialog.open()

    def create_rule_dialog(transaction_id: str) -> None:
        transaction = next(tx for tx in holder.state.transactions if tx.id == transaction_id)
        tx_flow = flow_type_for_amount(transaction.amount) or "outflow"
        catalog = holder.state.option_catalog()
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(f"Create {tx_flow} rule for: {transaction.description}").classes("font-bold")
            pattern = ui.input("Pattern", value=suggested_pattern(transaction.description)).classes("w-full")
            rule_type = ui.select([tx_flow], label="Rule type", value=tx_flow).classes("w-full")
            category_select, category_new = select_or_new("Category", category_options(tx_flow), transaction.category)
            owner_select, owner_new = select_or_new("Owner", catalog.owners, transaction.owner)
            priority = ui.number("Priority", value=0, format="%.0f").classes("w-full")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Save rule", on_click=lambda: save_rule(None, pattern, rule_type, category_select, category_new, owner_select, owner_new, priority, dialog))
        dialog.open()

    def manual_entry_dialog(flow_type: FlowType, transaction: Transaction | None = None) -> None:
        catalog = holder.state.option_catalog()
        initial_flow = transaction.flow_type if transaction else flow_type
        initial_date = transaction.date if transaction else ((filters.period and filters.period.year and filters.period.month and date(filters.period.year, filters.period.month, 1)) or date.today())
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(("Edit" if transaction else "Add") + f" {initial_flow}").classes("text-lg font-bold")
            rule_type = ui.select(["inflow", "outflow"], label="Flow type", value=initial_flow).classes("w-full")
            tx_date = ui.input("Date", value=initial_date.isoformat()).props("type=date").classes("w-full")
            description = ui.input("Description", value=transaction.description if transaction else "Manual entry").classes("w-full")
            amount = ui.number("Amount (enter positive number)", value=abs(transaction.amount) if transaction else 0.0, format="%.2f").classes("w-full")
            currency_select, currency_new = select_or_new("Currency", catalog.currencies, transaction.currency if transaction else DEFAULT_CURRENCY)
            account_select, account_new = select_or_new("Account/source", catalog.accounts, transaction.account if transaction else DEFAULT_ACCOUNT)
            category_select, category_new = select_or_new("Category", category_options(initial_flow), transaction.category if transaction else None)

            def update_manual_category_options(event) -> None:
                category_select.set_options(list(category_options(event.value)) + [OTHER_OPTION])

            rule_type.on_value_change(update_manual_category_options)
            owner_select, owner_new = select_or_new("Owner", catalog.owners, transaction.owner if transaction else "Shared")

            def save_manual() -> None:
                kwargs = dict(
                    flow_type=rule_type.value,
                    tx_date=date.fromisoformat(tx_date.value),
                    description=description.value,
                    amount=float(amount.value or 0),
                    currency=selected_value(currency_select, currency_new),
                    account=selected_value(account_select, account_new),
                    category=selected_value(category_select, category_new),
                    owner=selected_value(owner_select, owner_new),
                )
                set_state(holder.state.update_manual_transaction(transaction.id, **kwargs) if transaction else holder.state.add_manual_transaction(**kwargs))
                dialog.close()
                ui.notify("Manual entry saved.")

            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Save", on_click=save_manual)
        dialog.open()

    @ui.refreshable
    def content() -> None:
        with ui.column().classes("w-full gap-4"):
            with ui.row().classes("items-center"):
                ui.upload(label="Import CSV", auto_upload=True, multiple=True, on_upload=import_csv).props("accept=.csv").classes("max-w-sm")
                ui.upload(label="Import state", auto_upload=True, on_upload=import_state).props("accept=.json").classes("max-w-sm")
                ui.button("Export state", on_click=export_state)
                ui.button("Export merged CSV", on_click=export_csv)
                ui.button("Clear all data", color="negative", on_click=clear_state)

            if filters.period is None:
                filters.period = default_period_filter(holder.state.transactions)
            years = available_years(holder.state.transactions)
            if filters.period.year not in years:
                filters.period = default_period_filter(holder.state.transactions)
            with ui.card().classes("w-full"):
                ui.label("Manual entries period").classes("font-bold")
                with ui.row().classes("items-center"):
                    mode_select = ui.select(["all", "year", "month"], label="View", value=filters.period.mode).classes("w-32")
                    year_select = ui.select(list(years), label="Year", value=filters.period.year or years[-1]).classes("w-32")
                    month_select = ui.select(list(range(1, 13)), label="Month", value=filters.period.month or 1).classes("w-32")
                    month_select.visible = filters.period.mode == "month"
                    year_select.visible = filters.period.mode in ("year", "month")
                    def update_period() -> None:
                        filters.period = PeriodFilter(mode=mode_select.value, year=int(year_select.value) if mode_select.value in ("year", "month") else None, month=int(month_select.value) if mode_select.value == "month" else None)
                        content.refresh()
                    mode_select.on_value_change(lambda _: update_period())
                    year_select.on_value_change(lambda _: update_period())
                    month_select.on_value_change(lambda _: update_period())
                ui.label(f"Showing manual entries for: {filters.period.label}").classes("text-sm text-gray-600")

            ui.label("Manual cash-flow entries").classes("text-xl font-bold")
            with ui.row():
                ui.button("Add inflow", color="positive", on_click=lambda: manual_entry_dialog("inflow"))
                ui.button("Add outflow", color="primary", on_click=lambda: manual_entry_dialog("outflow"))
            manual_rows = [
                {
                    "id": tx.id,
                    "date": tx.date.isoformat(),
                    "flow_type": flow_label(tx.amount),
                    "description": tx.description,
                    "amount": f"{tx.amount:.2f}",
                    "currency": tx.currency,
                    "category": tx.category or "",
                    "owner": tx.owner or "",
                    "actions": "",
                }
                for tx in holder.state.transactions
                if tx.source_kind == "manual" and (filters.period is None or filters.period.includes(tx))
            ]
            if manual_rows:
                manual_table = ui.table(
                    columns=[
                        {"name": "date", "label": "Date", "field": "date", "align": "left"},
                        {"name": "flow_type", "label": "Flow type", "field": "flow_type", "align": "left"},
                        {"name": "description", "label": "Description", "field": "description", "align": "left"},
                        {"name": "amount", "label": "Amount", "field": "amount", "align": "right"},
                        {"name": "currency", "label": "Currency", "field": "currency"},
                        {"name": "category", "label": "Category", "field": "category", "align": "left"},
                        {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
                        {"name": "actions", "label": "Actions", "field": "actions"},
                    ],
                    rows=manual_rows,
                    row_key="id",
                ).classes("w-full")
                manual_table.add_slot("body-cell-actions", """
                    <q-td :props="props">
                      <q-btn dense flat color="primary" label="Edit" @click="$parent.$emit('edit', props.row.id)" />
                      <q-btn dense flat color="negative" label="Delete" @click="$parent.$emit('delete', props.row.id)" />
                    </q-td>
                """)
                manual_table.on("edit", lambda event: manual_entry_dialog("outflow", next(tx for tx in holder.state.transactions if tx.id == event.args)))
                manual_table.on("delete", lambda event: (set_state(holder.state.remove_manual_transaction(event.args)), ui.notify("Manual entry deleted.")))
            else:
                ui.label("No manual entries yet.").classes("text-gray-500")

            with ui.tabs().classes("w-full") as section_tabs:
                manual_tab = ui.tab("Manual entries")
                rules_tab = ui.tab("Rules")
                review_tab = ui.tab("Review unclassified")
            # Compact section anchors for scanning; content remains below so existing callbacks stay simple.

            ui.label("Rules").classes("text-xl font-bold")
            with ui.row():
                ui.button("Add inflow rule", on_click=lambda: rule_dialog(default_rule_type="inflow"))
                ui.button("Add outflow rule", on_click=lambda: rule_dialog(default_rule_type="outflow"))
            columns = [
                {"name": "pattern", "label": "Pattern", "field": "pattern", "align": "left"},
                {"name": "category", "label": "Category", "field": "category", "align": "left"},
                {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
                {"name": "rule_type", "label": "Rule type", "field": "rule_type"},
                {"name": "priority", "label": "Priority", "field": "priority"},
                {"name": "actions", "label": "Actions", "field": "actions"},
            ]
            rows = [{"id": rule.id, "pattern": rule.pattern, "category": rule.category, "owner": rule.owner, "rule_type": rule.rule_type, "priority": rule.priority, "actions": ""} for rule in holder.state.rules]
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
            review_rows = [tx for tx in holder.state.transactions if (tx.category is None or tx.owner is None) and not tx.ignored and flow_type_for_amount(tx.amount)]
            if not review_rows:
                ui.label("No unclassified transactions.").classes("text-gray-500")
            for tx in review_rows:
                with ui.card().classes("w-full"):
                    with ui.row().classes("items-center w-full"):
                        ui.label(tx.date.isoformat()).classes("w-24")
                        ui.label(flow_label(tx.amount)).classes("w-20 font-bold")
                        ui.label(tx.account).classes("w-32")
                        ui.label(tx.description).classes("grow")
                        ui.label(f"{tx.amount:.2f} {tx.currency}").classes("w-32 text-right")
                        ui.button("Assign", on_click=lambda _, tx_id=tx.id: assign_dialog(tx_id))
                        ui.button("Create rule", on_click=lambda _, tx_id=tx.id: create_rule_dialog(tx_id))
                        ui.button("Ignore", color="warning", on_click=lambda _, tx_id=tx.id: (set_state(holder.state.ignore_transaction(tx_id)), ui.notify("Transaction ignored.")))

    content()
    holder.refresh = content.refresh
