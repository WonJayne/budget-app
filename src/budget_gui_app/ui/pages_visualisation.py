"""NiceGUI visualisation page."""

from __future__ import annotations

import calendar
from datetime import date
from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from ..core.periods import PeriodFilter, available_years, default_period_filter
from ..core.sankey import DEFAULT_PALETTE, SankeyBuilder, category_colour, is_valid_hex_colour
from ..core.models import BudgetTarget
from ..core.state import AppState, DEFAULT_CURRENCY
from ..core.summaries import budget_comparison, budget_plan_totals, cash_flow_totals, included_transactions, summarize_transactions, transfer_monitor_totals, transfer_summary, yearly_overview


@dataclass
class Filters:
    period: PeriodFilter | None = None
    owner: str = "All"
    currency: str = "All"
    include_inflows: bool = True
    include_ignored: bool = False
    show_transfers: bool = False
    selected_colour_category: str | None = None
    selected_colour: str = DEFAULT_PALETTE[0]
    budget_year: int | None = None
    budget_month: int | None = None
    budget_currency: str = DEFAULT_CURRENCY


def build_visualisation_page(get_state: Callable[[], AppState], on_state_change: Callable[[AppState], None]) -> Callable[[], None]:
    filters = Filters()
    builder = SankeyBuilder()

    def options(state: AppState) -> tuple[tuple[int, ...], list[str], list[str]]:
        catalog = state.option_catalog()
        years = available_years(state.transactions)
        owners = ["All"] + list(catalog.owners)
        currency_options = ["All"] + list(catalog.currencies)
        if filters.currency not in currency_options:
            filters.currency = "CHF" if "CHF" in currency_options else "All"
        if filters.owner not in owners:
            filters.owner = "All"
        return years, owners, currency_options


    def budget_target_dialog(target: BudgetTarget | None = None) -> None:
        state = get_state()
        catalog = state.option_catalog()
        categories = sorted(set(catalog.inflow_categories) | set(catalog.outflow_categories))
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Edit budget target" if target else "Add budget target").classes("text-lg font-bold")
            name = ui.input("Name", value=target.name if target else "").classes("w-full")
            target_type = ui.select({"inflow": "Inflow", "outflow": "Outflow", "savings": "Savings"}, label="Type", value=target.target_type if target else "outflow").classes("w-full")
            category = ui.select([""] + categories, label="Category", value=target.category if target and target.category else "").props("use-input new-value-mode=add-unique").classes("w-full")
            owner = ui.select([""] + list(catalog.owners), label="Owner", value=target.owner if target and target.owner else "").props("use-input new-value-mode=add-unique").classes("w-full")
            currency = ui.select(list(catalog.currencies), label="Currency", value=target.currency if target else DEFAULT_CURRENCY).props("use-input new-value-mode=add-unique").classes("w-full")
            monthly_amount = ui.number("Monthly amount", value=target.monthly_amount if target else 0.0, format="%.2f").classes("w-full")
            active = ui.switch("Active", value=target.active if target else True)
            notes = ui.input("Notes", value=target.notes if target and target.notes else "").classes("w-full")

            def save() -> None:
                saved = BudgetTarget(
                    id=target.id if target else BudgetTarget.make_id(name.value or "Budget target", target_type.value, currency.value, str(len(state.budget_targets))),
                    name=name.value or "Budget target",
                    target_type=target_type.value,
                    category=category.value or None,
                    owner=owner.value or None,
                    currency=currency.value,
                    monthly_amount=float(monthly_amount.value or 0),
                    active=bool(active.value),
                    notes=notes.value or None,
                )
                on_state_change(get_state().update_budget_target(saved) if target else get_state().add_budget_target(saved))
                dialog.close()
                ui.notify("Budget target saved.")

            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Save", on_click=save)
        dialog.open()

    def budget_section(state: AppState, years: tuple[int, ...], currencies: list[str]) -> None:
        today = date.today()
        if filters.budget_year is None:
            filters.budget_year = (filters.period.year if filters.period and filters.period.year else today.year)
        if filters.budget_month is None:
            filters.budget_month = (filters.period.month if filters.period and filters.period.month else today.month)
        if filters.budget_currency not in currencies or filters.budget_currency == "All":
            filters.budget_currency = "CHF" if "CHF" in currencies else (currencies[1] if len(currencies) > 1 else DEFAULT_CURRENCY)
        with ui.expansion("Budget / Plan", icon="savings", value=True).classes("w-full"):
            ui.label("Monthly budget targets compare your plan with actuals and a simple linear month-end projection. Transfers and ignored transactions are excluded by default.").classes("text-sm text-gray-600")
            with ui.row().classes("items-center"):
                ui.select(list(years), label="Year", value=filters.budget_year, on_change=lambda event: (setattr(filters, "budget_year", int(event.value)), content.refresh())).classes("w-32")
                ui.select(list(range(1, 13)), label="Month", value=filters.budget_month, on_change=lambda event: (setattr(filters, "budget_month", int(event.value)), content.refresh())).classes("w-32")
                ui.select([c for c in currencies if c != "All"], label="Currency", value=filters.budget_currency, on_change=lambda event: (setattr(filters, "budget_currency", event.value), content.refresh())).classes("w-36")
                ui.button("Add target", on_click=lambda: budget_target_dialog())
            totals = budget_plan_totals(state.transactions, state.budget_targets, filters.budget_year, filters.budget_month, filters.budget_currency, today)
            with ui.row().classes("gap-4"):
                for label, value in (("Planned inflow", totals.planned_inflow), ("Projected inflow", totals.projected_inflow), ("Planned outflow", totals.planned_outflow), ("Projected outflow", totals.projected_outflow), ("Planned savings", totals.planned_savings), ("Projected savings", totals.projected_savings), ("Projected budget variance", totals.projected_budget_variance)):
                    with ui.card().classes("min-w-40"):
                        ui.label(label).classes("text-sm text-gray-600")
                        ui.label(f"{value:.2f} {filters.budget_currency}").classes("text-lg font-bold")
            rows = [
                {"target": row.target_name, "type": row.target_type, "category": row.category or "All", "owner": row.owner or "All", "budget": f"{row.budget:.2f}", "actual": f"{row.actual:.2f}", "projected": f"{row.projected:.2f}", "difference": f"{row.difference:.2f}", "status": row.status}
                for row in budget_comparison(state.transactions, state.budget_targets, filters.budget_year, filters.budget_month, filters.budget_currency, today)
            ]
            ui.table(columns=[
                {"name": "target", "label": "Target", "field": "target", "align": "left"},
                {"name": "type", "label": "Type", "field": "type"},
                {"name": "category", "label": "Category", "field": "category", "align": "left"},
                {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
                {"name": "budget", "label": "Budget", "field": "budget", "align": "right"},
                {"name": "actual", "label": "Actual", "field": "actual", "align": "right"},
                {"name": "projected", "label": "Projected month-end", "field": "projected", "align": "right"},
                {"name": "difference", "label": "Difference", "field": "difference", "align": "right"},
                {"name": "status", "label": "Status", "field": "status"},
            ], rows=rows).classes("w-full")
            for target in state.budget_targets:
                if target.currency == filters.budget_currency:
                    with ui.row().classes("items-center gap-2"):
                        ui.label(f"{target.name} ({'active' if target.active else 'inactive'})")
                        ui.button("Edit", on_click=lambda _, t=target: budget_target_dialog(t))
                        ui.button("Delete", color="negative", on_click=lambda _, t=target: on_state_change(get_state().remove_budget_target(t.id)))
            ui.label("Projection is a simple linear month-to-date estimate; it is most useful for variable outflows and less reliable for one-off or fixed monthly payments.").classes("text-xs text-gray-500")

    def period_controls(years: tuple[int, ...]) -> None:
        assert filters.period is not None
        with ui.row().classes("items-center"):
            mode = ui.select(["all", "year", "month"], label="View", value=filters.period.mode).classes("w-32")
            year = ui.select(list(years), label="Year", value=filters.period.year or years[-1]).classes("w-32")
            month = ui.select(list(range(1, 13)), label="Month", value=filters.period.month or 1).classes("w-32")
            year.visible = filters.period.mode in ("year", "month")
            month.visible = filters.period.mode == "month"

            def update() -> None:
                filters.period = PeriodFilter(
                    mode=mode.value,
                    year=int(year.value) if mode.value in ("year", "month") else None,
                    month=int(month.value) if mode.value == "month" else None,
                )
                content.refresh()

            mode.on_value_change(lambda _: update())
            year.on_value_change(lambda _: update())
            month.on_value_change(lambda _: update())

    @ui.refreshable
    def content() -> None:
        state = get_state()
        if filters.period is None:
            filters.period = default_period_filter(state.transactions)
        years, owners, currencies = options(state)
        if filters.period.year not in years and filters.period.mode != "all":
            filters.period = default_period_filter(state.transactions)

        owner_value = None if filters.owner == "All" else filters.owner
        currency_value = None if filters.currency == "All" else filters.currency
        included = included_transactions(
            state.transactions,
            period=filters.period,
            owner=owner_value,
            currency=currency_value,
            include_inflows=filters.include_inflows,
            include_ignored=filters.include_ignored,
        )
        totals = cash_flow_totals(included)
        transfer_included = included_transactions(
            state.transactions,
            period=filters.period,
            owner=owner_value,
            currency=currency_value,
            include_inflows=True,
            include_ignored=filters.include_ignored,
            include_transfers=True,
        )
        transfer_rows_raw = transfer_summary(transfer_included)
        transfer_totals = transfer_monitor_totals(transfer_rows_raw)
        transfer_count = transfer_totals.transfer_count

        with ui.column().classes("w-full gap-4"):
            with ui.card().classes("w-full"):
                ui.label("Period and filters").classes("text-lg font-bold")
                period_controls(years)
                with ui.row().classes("items-center"):
                    ui.select(owners, label="Owner", value=filters.owner, on_change=lambda event: (setattr(filters, "owner", event.value), content.refresh())).classes("w-36")
                    ui.select(currencies, label="Currency", value=filters.currency, on_change=lambda event: (setattr(filters, "currency", event.value), content.refresh())).classes("w-36")
                    ui.switch("Include inflows", value=filters.include_inflows, on_change=lambda event: (setattr(filters, "include_inflows", event.value), content.refresh()))
                    ui.switch("Include ignored", value=filters.include_ignored, on_change=lambda event: (setattr(filters, "include_ignored", event.value), content.refresh()))
                    ui.switch("Show internal transfers", value=filters.show_transfers, on_change=lambda event: (setattr(filters, "show_transfers", event.value), content.refresh()))
                ui.label(f"Showing: {filters.period.label} • Currency: {filters.currency} • Owners: {filters.owner}").classes("text-sm text-gray-600")

            budget_section(state, years, currencies)

            with ui.row().classes("gap-4"):
                for label, value in (
                    ("Total inflow", totals.total_inflow),
                    ("Total outflow", totals.total_outflow),
                    ("Balance", totals.balance),
                    ("Potential savings", totals.potential_savings),
                    ("Deficit", totals.deficit),
                ):
                    with ui.card().classes("min-w-40"):
                        ui.label(label).classes("text-sm text-gray-500")
                        ui.label(f"{value:.2f}").classes("text-xl font-bold")

            with ui.tabs().classes("w-full") as tabs:
                sankey_tab = ui.tab("Sankey")
                yearly_tab = ui.tab("Yearly overview")
                category_tab = ui.tab("Category summary")
            with ui.tab_panels(tabs, value=sankey_tab).classes("w-full"):
                with ui.tab_panel(sankey_tab):
                    ui.label(f"Showing: {filters.period.label} | Currency: {filters.currency} | Owners: {filters.owner}").classes("font-bold")
                    figure = builder.build(
                        state.transactions,
                        state.category_style_map(),
                        period=filters.period,
                        owner=owner_value,
                        currency=currency_value,
                        include_inflows=filters.include_inflows,
                        include_ignored=filters.include_ignored,
                    )
                    ui.plotly(figure).classes("w-full h-[560px]")
                    if filters.show_transfers or transfer_count:
                        with ui.card().classes("w-full mt-4"):
                            ui.label("Internal transfer monitor").classes("text-lg font-bold")
                            ui.label("Internal transfers are excluded from household inflow/outflow totals. They are shown here only for monitoring movements between own accounts or pools.").classes("text-sm text-gray-600")
                            with ui.row().classes("gap-4"):
                                for label, value in (
                                    ("Matched internal transfers", transfer_totals.matched_transfers),
                                    ("Unmatched transfer in", transfer_totals.unmatched_transfer_inflow),
                                    ("Unmatched transfer out", transfer_totals.unmatched_transfer_outflow),
                                    ("Net internal movement", transfer_totals.net_transfer_movement),
                                    ("Absolute internal movement", transfer_totals.absolute_transfer_movement),
                                ):
                                    with ui.card().classes("min-w-40"):
                                        ui.label(label).classes("text-sm text-gray-500")
                                        ui.label(f"{value:.2f}").classes("text-xl font-bold")
                                with ui.card().classes("min-w-40"):
                                    ui.label("Transfer count").classes("text-sm text-gray-500")
                                    ui.label(str(transfer_count)).classes("text-xl font-bold")
                            transfer_rows = [
                                {
                                    "group_id": row.group_id,
                                    "status": row.status,
                                    "currency": row.currency,
                                    "count": row.count,
                                    "transfer_inflow": f"{row.transfer_inflow:.2f}",
                                    "transfer_outflow": f"{row.transfer_outflow:.2f}",
                                    "matched_amount": f"{row.matched_amount:.2f}",
                                    "unmatched_inflow": f"{row.unmatched_inflow:.2f}",
                                    "unmatched_outflow": f"{row.unmatched_outflow:.2f}",
                                    "net_movement": f"{row.net_movement:.2f}",
                                    "absolute_movement": f"{row.absolute_movement:.2f}",
                                    "category": row.category,
                                    "owner": row.owner,
                                }
                                for row in transfer_rows_raw
                            ]
                            ui.table(columns=[
                                {"name": "group_id", "label": "Transfer group", "field": "group_id", "align": "left"},
                                {"name": "status", "label": "Status", "field": "status", "align": "left"},
                                {"name": "currency", "label": "Currency", "field": "currency"},
                                {"name": "count", "label": "Count", "field": "count", "align": "right"},
                                {"name": "transfer_inflow", "label": "Internal transfer in", "field": "transfer_inflow", "align": "right"},
                                {"name": "transfer_outflow", "label": "Internal transfer out", "field": "transfer_outflow", "align": "right"},
                                {"name": "matched_amount", "label": "Matched amount", "field": "matched_amount", "align": "right"},
                                {"name": "unmatched_inflow", "label": "Unmatched transfer in", "field": "unmatched_inflow", "align": "right"},
                                {"name": "unmatched_outflow", "label": "Unmatched transfer out", "field": "unmatched_outflow", "align": "right"},
                                {"name": "net_movement", "label": "Net internal movement", "field": "net_movement", "align": "right"},
                                {"name": "absolute_movement", "label": "Absolute internal movement", "field": "absolute_movement", "align": "right"},
                                {"name": "category", "label": "Category", "field": "category", "align": "left"},
                                {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
                            ], rows=transfer_rows).classes("w-full")
                with ui.tab_panel(yearly_tab):
                    selected_year = filters.period.year or years[-1]
                    ui.label(f"Yearly overview for {selected_year}").classes("font-bold")
                    rows = [
                        {
                            "month": calendar.month_abbr[row.month],
                            "total_inflow": f"{row.total_inflow:.2f}",
                            "total_outflow": f"{row.total_outflow:.2f}",
                            "balance": f"{row.balance:.2f}",
                            "potential_savings": f"{row.potential_savings:.2f}",
                            "deficit": f"{row.deficit:.2f}",
                            "transfer_count": row.transfer_count,
                            "matched_transfers": f"{row.matched_transfers:.2f}",
                            "unmatched_transfer_inflow": f"{row.unmatched_transfer_inflow:.2f}",
                            "unmatched_transfer_outflow": f"{row.unmatched_transfer_outflow:.2f}",
                            "transfer_absolute_movement": f"{row.transfer_absolute_movement:.2f}",
                            "transfer_net_movement": f"{row.transfer_net_movement:.2f}",
                        }
                        for row in yearly_overview(state.transactions, selected_year, currency=currency_value, include_ignored=filters.include_ignored)
                    ]
                    ui.table(columns=[
                        {"name": "month", "label": "Month", "field": "month"},
                        {"name": "total_inflow", "label": "Total inflow", "field": "total_inflow", "align": "right"},
                        {"name": "total_outflow", "label": "Total outflow", "field": "total_outflow", "align": "right"},
                        {"name": "balance", "label": "Balance", "field": "balance", "align": "right"},
                        {"name": "potential_savings", "label": "Potential savings", "field": "potential_savings", "align": "right"},
                        {"name": "deficit", "label": "Deficit", "field": "deficit", "align": "right"},
                        {"name": "transfer_count", "label": "Transfer count", "field": "transfer_count", "align": "right"},
                        {"name": "matched_transfers", "label": "Matched internal transfers", "field": "matched_transfers", "align": "right"},
                        {"name": "unmatched_transfer_inflow", "label": "Unmatched transfer in", "field": "unmatched_transfer_inflow", "align": "right"},
                        {"name": "unmatched_transfer_outflow", "label": "Unmatched transfer out", "field": "unmatched_transfer_outflow", "align": "right"},
                        {"name": "transfer_absolute_movement", "label": "Absolute internal movement", "field": "transfer_absolute_movement", "align": "right"},
                        {"name": "transfer_net_movement", "label": "Net internal movement", "field": "transfer_net_movement", "align": "right"},
                    ], rows=rows).classes("w-full")
                with ui.tab_panel(category_tab):
                    selected_year = filters.period.year or years[-1]
                    period = PeriodFilter("year", selected_year)
                    yearly_included = included_transactions(state.transactions, period=period, owner=owner_value, currency=currency_value, include_inflows=True, include_ignored=filters.include_ignored)
                    yearly_totals = cash_flow_totals(yearly_included)
                    rows = []
                    for row in summarize_transactions(state.transactions, period=period, owner=owner_value, currency=currency_value, include_inflows=True, include_ignored=filters.include_ignored):
                        denominator = yearly_totals.total_inflow if row.flow_type == "inflow" else yearly_totals.total_outflow
                        share = abs(row.total_amount) / denominator if denominator else 0.0
                        rows.append({"flow_type": row.flow_type, "category": row.category, "owner": row.owner, "total_amount": f"{row.total_amount:.2f}", "share": f"{share:.1%}"})
                    ui.table(columns=[
                        {"name": "category", "label": "Category", "field": "category", "align": "left"},
                        {"name": "flow_type", "label": "Flow type", "field": "flow_type"},
                        {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
                        {"name": "total_amount", "label": "Total amount", "field": "total_amount", "align": "right"},
                        {"name": "share", "label": "Share of yearly flow", "field": "share", "align": "right"},
                    ], rows=rows).classes("w-full")


            with ui.expansion("Category colour editor", icon="palette").classes("w-full"):
                catalog = state.option_catalog()
                categories = sorted(set(catalog.inflow_categories) | set(catalog.outflow_categories) | set(state.category_style_map()))
                if not categories:
                    ui.label("No categories yet.").classes("text-gray-500")
                else:
                    if filters.selected_colour_category not in categories:
                        filters.selected_colour_category = categories[0]
                    styles = state.category_style_map()
                    saved_colour = styles.get(filters.selected_colour_category).colour if filters.selected_colour_category in styles else None
                    fallback_colour = category_colour(filters.selected_colour_category, styles)
                    preview_colour = filters.selected_colour if is_valid_hex_colour(filters.selected_colour) else saved_colour or fallback_colour

                    def select_category(event) -> None:
                        setattr(filters, "selected_colour_category", event.value)
                        new_saved = styles.get(event.value).colour if event.value in styles else None
                        setattr(filters, "selected_colour", new_saved or category_colour(event.value, styles))
                        content.refresh()

                    def save_colour() -> None:
                        if not is_valid_hex_colour(filters.selected_colour):
                            ui.notify("Enter a valid custom colour in #RRGGBB format before saving.", color="negative")
                            return
                        on_state_change(get_state().set_category_colour(filters.selected_colour_category or categories[0], filters.selected_colour))
                        ui.notify("Colour saved.")

                    ui.select(categories, label="Category", value=filters.selected_colour_category, on_change=select_category).classes("w-72")
                    with ui.row().classes("items-center gap-3"):
                        ui.label("Current colour:")
                        ui.label(" ").style(f"background-color:{preview_colour}; width:64px; height:36px; border-radius:8px; border:2px solid #374151;")
                        ui.label(preview_colour).classes("font-mono text-sm")
                        if saved_colour:
                            ui.label("custom saved").classes("text-xs text-green-700")
                        else:
                            ui.label("automatic fallback until saved").classes("text-xs text-gray-500")
                    ui.label("Palette").classes("font-bold")
                    with ui.row().classes("gap-2 items-center"):
                        for colour in DEFAULT_PALETTE:
                            selected = colour.lower() == preview_colour.lower()
                            chip = ui.button("✓" if selected else "", on_click=lambda _, c=colour: (setattr(filters, "selected_colour", c), content.refresh()))
                            chip.props(f'aria-label="{colour}" title="{colour}"')
                            chip.style(
                                f"background-color: {colour}; color: white; width: 34px; height: 34px; min-width: 34px; "
                                f"border-radius: 8px; border: {'3px solid #111827' if selected else '2px solid #ffffff'}; "
                                "box-shadow: 0 1px 4px rgba(0,0,0,0.25);"
                            )
                    with ui.expansion("Advanced custom hex"):
                        ui.input("Custom hex colour", value=filters.selected_colour, on_change=lambda event: setattr(filters, "selected_colour", event.value), placeholder="#RRGGBB").classes("w-40")
                        ui.color_input("Native colour picker", value=preview_colour, on_change=lambda event: (setattr(filters, "selected_colour", event.value), content.refresh())).classes("w-40")
                    with ui.row():
                        ui.button("Save colour", color="primary", on_click=save_colour)
                        ui.button("Reset to automatic", on_click=lambda: (on_state_change(get_state().set_category_colour(filters.selected_colour_category or categories[0], None)), setattr(filters, "selected_colour", category_colour(filters.selected_colour_category or categories[0], get_state().category_style_map())), ui.notify("Colour reset.")))

    content()
    return content.refresh
