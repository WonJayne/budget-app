"""NiceGUI visualisation page."""

from __future__ import annotations

import calendar
from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from ..core.periods import PeriodFilter, available_years, default_period_filter
from ..core.sankey import DEFAULT_NODE_COLOUR, SankeyBuilder
from ..core.state import AppState
from ..core.summaries import cash_flow_totals, included_transactions, summarize_transactions, transfer_summary, yearly_overview
DEFAULT_PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756",
    "#72B7B2", "#B279A2", "#FF9DA6", "#9D755D",
    "#BAB0AC", "#A0CBE8", "#FFBE7D", "#8CD17D",
    "#D4A6C8", "#F1CE63", "#499894", "#86BCB6",
]


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
                        include_transfers=filters.show_transfers,
                    )
                    ui.plotly(figure).classes("w-full h-[560px]")
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
                            "transfer_absolute_movement": f"{row.transfer_absolute_movement:.2f}",
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
                        {"name": "transfer_absolute_movement", "label": "Transfer movement", "field": "transfer_absolute_movement", "align": "right"},
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
                    transfer_rows = [
                        {
                            "category": row.category,
                            "owner": row.owner,
                            "count": row.count,
                            "net_amount": f"{row.net_amount:.2f}",
                            "absolute_movement": f"{row.absolute_movement:.2f}",
                        }
                        for row in transfer_summary(included_transactions(state.transactions, period=filters.period, owner=owner_value, currency=currency_value, include_inflows=True, include_ignored=filters.include_ignored, include_transfers=True))
                    ]
                    if transfer_rows:
                        ui.label("Internal transfer summary").classes("font-bold mt-4")
                        ui.label("Transfers are neutral by default and excluded from household inflow/outflow totals.").classes("text-sm text-gray-600")
                        ui.table(columns=[
                            {"name": "category", "label": "Category", "field": "category", "align": "left"},
                            {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
                            {"name": "count", "label": "Count", "field": "count", "align": "right"},
                            {"name": "net_amount", "label": "Net amount", "field": "net_amount", "align": "right"},
                            {"name": "absolute_movement", "label": "Absolute movement", "field": "absolute_movement", "align": "right"},
                        ], rows=transfer_rows).classes("w-full")


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
                    preview_colour = filters.selected_colour or saved_colour or DEFAULT_NODE_COLOUR
                    ui.select(categories, label="Category", value=filters.selected_colour_category, on_change=lambda event: (setattr(filters, "selected_colour_category", event.value), setattr(filters, "selected_colour", styles.get(event.value).colour if event.value in styles else DEFAULT_PALETTE[0]), content.refresh())).classes("w-72")
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
                                f"background-color:{colour}; color:white; width:32px; height:32px; min-width:32px; "
                                f"border-radius:6px; border:{'3px solid #111827' if selected else '1px solid #d1d5db'};"
                            )
                    with ui.expansion("Advanced custom hex"):
                        colour_input = ui.input("Custom hex colour", value=filters.selected_colour, on_change=lambda event: setattr(filters, "selected_colour", event.value)).classes("w-40")
                        ui.color_input("Native colour picker", value=preview_colour, on_change=lambda event: (setattr(filters, "selected_colour", event.value), content.refresh())).classes("w-40")
                    with ui.row():
                        ui.button("Save colour", color="primary", on_click=lambda: (on_state_change(get_state().set_category_colour(filters.selected_colour_category or categories[0], filters.selected_colour)), ui.notify("Colour saved.")))
                        ui.button("Reset to automatic", on_click=lambda: (on_state_change(get_state().set_category_colour(filters.selected_colour_category or categories[0], None)), setattr(filters, "selected_colour", DEFAULT_PALETTE[0]), ui.notify("Colour reset.")))

    content()
    return content.refresh
