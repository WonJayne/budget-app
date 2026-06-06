"""NiceGUI visualisation page."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from ..core.sankey import SankeyBuilder
from ..core.state import AppState
from ..core.summaries import cash_flow_totals, included_transactions, summarize_transactions
from .pages_data import select_or_new, selected_value


@dataclass
class Filters:
    month: str = "All"
    owner: str = "All"
    currency: str = "All"
    include_inflows: bool = True
    include_ignored: bool = False


def build_visualisation_page(get_state: Callable[[], AppState], on_state_change: Callable[[AppState], None]) -> Callable[[], None]:
    filters = Filters()
    builder = SankeyBuilder()

    def options(state: AppState) -> tuple[list[str], list[str], list[str]]:
        catalog = state.option_catalog()
        months = ["All"] + sorted({tx.date.strftime("%Y-%m") for tx in state.transactions})
        owners = ["All"] + list(catalog.owners)
        currency_options = ["All"] + list(catalog.currencies)
        if filters.currency not in currency_options:
            filters.currency = "CHF" if "CHF" in currency_options else "All"
        return months, owners, currency_options

    @ui.refreshable
    def content() -> None:
        state: AppState = get_state()
        months, owners, currencies = options(state)
        if filters.month not in months:
            filters.month = "All"
        if filters.owner not in owners:
            filters.owner = "All"

        month_value = None if filters.month == "All" else filters.month
        owner_value = None if filters.owner == "All" else filters.owner
        currency_value = None if filters.currency == "All" else filters.currency
        included = included_transactions(
            state.transactions,
            month=month_value,
            owner=owner_value,
            currency=currency_value,
            include_inflows=filters.include_inflows,
            include_ignored=filters.include_ignored,
        )
        totals = cash_flow_totals(included)

        with ui.column().classes("w-full gap-4"):
            with ui.row().classes("items-center"):
                ui.select(months, label="Month", value=filters.month, on_change=lambda event: (setattr(filters, "month", event.value), content.refresh())).classes("w-36")
                ui.select(owners, label="Owner", value=filters.owner, on_change=lambda event: (setattr(filters, "owner", event.value), content.refresh())).classes("w-36")
                ui.select(currencies, label="Currency", value=filters.currency, on_change=lambda event: (setattr(filters, "currency", event.value), content.refresh())).classes("w-36")
                ui.switch("Include inflows", value=filters.include_inflows, on_change=lambda event: (setattr(filters, "include_inflows", event.value), content.refresh()))
                ui.switch("Include ignored", value=filters.include_ignored, on_change=lambda event: (setattr(filters, "include_ignored", event.value), content.refresh()))

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

            figure = builder.build(
                state.transactions,
                state.category_style_map(),
                month=month_value,
                owner=owner_value,
                currency=currency_value,
                include_inflows=filters.include_inflows,
                include_ignored=filters.include_ignored,
            )
            ui.plotly(figure).classes("w-full h-[520px]")

            ui.label("Category colours").classes("text-xl font-bold")
            catalog = state.option_catalog()
            categories = sorted(set(catalog.inflow_categories) | set(catalog.outflow_categories))
            styles = state.category_style_map()
            if not categories:
                ui.label("No categories yet.").classes("text-gray-500")
            for category in categories:
                with ui.row().classes("items-center"):
                    ui.label(category).classes("w-48")
                    colour = ui.input("Hex colour", value=styles.get(category).colour if category in styles else "").classes("w-40")
                    ui.button("Save", on_click=lambda _, cat=category, inp=colour: (on_state_change(get_state().set_category_colour(cat, inp.value or None)), ui.notify("Colour saved.")))
            with ui.expansion("Add colour for new category", icon="palette"):
                category_select, category_new = select_or_new("Category", categories, None)
                colour = ui.input("Hex colour", value="#9ca3af").classes("w-40")
                ui.button("Save colour", on_click=lambda: (on_state_change(get_state().set_category_colour(selected_value(category_select, category_new), colour.value or None)), ui.notify("Colour saved.")))

            ui.label("Summary").classes("text-xl font-bold")
            rows = [
                {
                    "flow_type": row.flow_type,
                    "category": row.category,
                    "owner": row.owner,
                    "total_amount": f"{row.total_amount:.2f}",
                    "share_of_outflows": f"{row.share_of_outflows:.1%}",
                }
                for row in summarize_transactions(
                    state.transactions,
                    month=month_value,
                    owner=owner_value,
                    currency=currency_value,
                    include_inflows=filters.include_inflows,
                    include_ignored=filters.include_ignored,
                )
            ]
            ui.table(
                columns=[
                    {"name": "flow_type", "label": "Flow type", "field": "flow_type", "align": "left"},
                    {"name": "category", "label": "Category", "field": "category", "align": "left"},
                    {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
                    {"name": "total_amount", "label": "Total amount", "field": "total_amount", "align": "right"},
                    {"name": "share_of_outflows", "label": "Share of outflows", "field": "share_of_outflows", "align": "right"},
                ],
                rows=rows,
            ).classes("w-full")

    content()
    return content.refresh
