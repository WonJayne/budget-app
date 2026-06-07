"""Local-only NiceGUI interface for the budget application."""

from __future__ import annotations

from datetime import date

from nicegui import ui

from ..core.models import Rule, Transaction
from ..core.state import AppState
from .pages_data import UiState, build_data_page
from .pages_visualisation import build_visualisation_page


def demo_state() -> AppState:
    rows = (
        Transaction("demo-flo-salary-jul", date(2026, 7, 25), "demo", "Flo salary", 6500, "CHF", source_file="demo", category="Salary", owner="Flo", assignment_source="manual"),
        Transaction("demo-nina-salary-jul", date(2026, 7, 25), "demo", "Nina salary", 5200, "CHF", source_file="demo", category="Salary", owner="Nina", assignment_source="manual"),
        Transaction("demo-gift-jul", date(2026, 7, 10), "demo", "Shared gift", 500, "CHF", source_file="demo", category="Gift", owner="Shared", assignment_source="manual"),
        Transaction("demo-groceries-jul", date(2026, 7, 5), "demo", "Groceries", -1300, "CHF", source_file="demo", category="Groceries", owner="Shared", assignment_source="manual"),
        Transaction("demo-insurance-jul", date(2026, 7, 8), "demo", "Insurance", -800, "CHF", source_file="demo", category="Insurance", owner="Shared", assignment_source="manual"),
        Transaction("demo-transport-jul", date(2026, 7, 12), "demo", "Transport", -420, "CHF", source_file="demo", category="Transport", owner="Shared", assignment_source="manual"),
        Transaction("demo-invest-jul", date(2026, 7, 28), "demo", "Investments", -2500, "CHF", source_file="demo", category="Investments", owner="Shared", assignment_source="manual"),
        Transaction("demo-transfer-out-jul", date(2026, 7, 29), "demo shared", "Credit card settlement", -1200, "CHF", source_file="demo", import_source="Demo shared account", cash_flow_type="transfer", category="Credit card settlement", owner="Shared", assignment_source="manual", transfer_group_id="cc-settlement-2026-07", transfer_note="Shared account pays credit card"),
        Transaction("demo-transfer-in-jul", date(2026, 7, 30), "demo card", "Credit card settlement received", 1200, "CHF", source_file="demo", import_source="Demo credit card", cash_flow_type="transfer", category="Credit card settlement", owner="Shared", assignment_source="manual", transfer_group_id="cc-settlement-2026-07", transfer_note="Credit card side of settlement"),
        Transaction("demo-flo-salary-aug", date(2026, 8, 25), "demo", "Flo salary", 6500, "CHF", source_file="demo", category="Salary", owner="Flo", assignment_source="manual"),
        Transaction("demo-nina-salary-aug", date(2026, 8, 25), "demo", "Nina salary", 5200, "CHF", source_file="demo", category="Salary", owner="Nina", assignment_source="manual"),
        Transaction("demo-groceries-aug", date(2026, 8, 5), "demo", "Groceries", -1450, "CHF", source_file="demo", category="Groceries", owner="Shared", assignment_source="manual"),
        Transaction("demo-holidays-aug", date(2026, 8, 15), "demo", "Holidays", -9000, "CHF", source_file="demo", category="Holidays", owner="Shared", assignment_source="manual"),
        Transaction("demo-transport-aug", date(2026, 8, 12), "demo", "Transport", -550, "CHF", source_file="demo", category="Transport", owner="Shared", assignment_source="manual"),
        Transaction("demo-insurance-aug", date(2026, 8, 8), "demo", "Insurance", -2100, "CHF", source_file="demo", category="Insurance", owner="Shared", assignment_source="manual"),
    )
    rules = (
        Rule(Rule.make_id("salary", "Salary", "Shared", "inflow"), "salary", "Salary", "Shared", "inflow", 10),
        Rule(Rule.make_id("groceries", "Groceries", "Shared", "outflow"), "groceries", "Groceries", "Shared", "outflow", 10),
    )
    return AppState(transactions=rows, rules=rules)


def build_help_page(holder: UiState, set_state) -> None:
    def load_demo() -> None:
        if holder.state.transactions or holder.state.rules:
            with ui.dialog() as dialog, ui.card():
                ui.label("Replace current data with demo data?")
                with ui.row():
                    ui.button("Cancel", on_click=dialog.close)
                    ui.button("Load demo data", color="primary", on_click=lambda: (set_state(demo_state()), dialog.close(), ui.notify("Demo data loaded.")))
            dialog.open()
        else:
            set_state(demo_state())
            ui.notify("Demo data loaded.")

    with ui.column().classes("w-full gap-4"):
        ui.label("How it works").classes("text-2xl font-bold")
        ui.markdown("""
- Import transactions CSV files or add manual entries as **Inflow**, **Outflow**, **Internal transfer in**, or **Internal transfer out**. Each CSV import gets a stable **import source** label, defaulting to the uploaded filename stem, so rules can target one bank/card feed. Export a ledger CSV for spreadsheet use, a full backup JSON to stop and restart later, or a rules/profile JSON to reuse classifications and colours without changing transactions.
- Positive stored amounts are **inflows** or **internal transfer in** movements; negative stored amounts are **outflows** or **internal transfer out** movements. The entry dialogs treat the typed amount as absolute and use the selected flow type to set the sign. **Internal transfers** are movements between your own tracked accounts/pools, such as credit card settlements, savings transfers, brokerage transfers, or personal-to-shared transfers. They are neutral by default and excluded from inflow, outflow, balance, **Potential savings**, and **Deficit** totals.
- If both sides are imported, classify both rows as internal transfers and give them the same **Transfer group** so the transfer monitor can show a balanced pair. If only one side is imported, the monitor marks it as single-sided/unmatched; this does not affect budget totals, but it tells you the tracked data does not contain both sides.
- If money from Flo/Nina enters a shared household account and the private account is **not** tracked in this app, classify the received money as an inflow/contribution (for example `Flo contribution`) if you want it to fund the household budget. Use transfer only when you intentionally want the movement excluded from budget totals.
- Rules can be global with Source = **Any** or source-scoped to an observed import source. Rule applicability is selected as **Inflow**, **Outflow**, **Any internal transfer**, **Internal transfer in**, or **Internal transfer out**. Manual assignments and transfer groups/notes survive rule changes.
- Cash flows into the **Household pool**. Extra money becomes **Potential savings**; overspending appears as **Deficit**. Transfers stay outside ordinary budget flows and are shown in the internal transfer monitor; enabling the transfer toggle keeps them as a separate neutral monitoring layer.
- Monthly view focuses on one household budget month. Yearly view aggregates all months in the selected year.
- Full backup import/export saves and restores transactions, rules, manual entries, ignored flags, metadata, and category colours. Rules/profile import/export contains rules and colours but no transaction data.
- Category colours are edited from the Visualisation page: choose a category from the dropdown, click a visible palette colour, and save. The advanced `#RRGGBB` hex input is optional and invalid custom colours are rejected.
""")
        ui.button("Load demo data", color="primary", on_click=load_demo)


def create_ui() -> None:
    holder = UiState(state=AppState.empty(), refresh=lambda: None)
    refreshers: list = []

    def refresh_all() -> None:
        for refresh in refreshers:
            refresh()

    def set_state(state: AppState) -> None:
        holder.state = state
        refresh_all()

    holder.refresh = refresh_all

    ui.page_title("Budget App")
    ui.label("Household Budget App").classes("text-2xl font-bold mb-4")
    with ui.tabs().classes("w-full") as tabs:
        data_tab = ui.tab("Data / Rules / Review")
        visualisation_tab = ui.tab("Visualisation")
        help_tab = ui.tab("How it works")
    with ui.tab_panels(tabs, value=data_tab).classes("w-full"):
        with ui.tab_panel(data_tab):
            build_data_page(holder)
            refreshers.append(holder.refresh)
        with ui.tab_panel(visualisation_tab):
            viz_refresh = build_visualisation_page(lambda: holder.state, set_state)
            refreshers.append(viz_refresh)
        with ui.tab_panel(help_tab):
            build_help_page(holder, set_state)

    holder.refresh = refresh_all


def main() -> None:
    ui.run(root=create_ui, host="127.0.0.1", port=8080, reload=False)


run_app = main
build_ui = create_ui
