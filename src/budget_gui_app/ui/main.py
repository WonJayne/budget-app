"""Local-only NiceGUI interface for the budget application."""

from __future__ import annotations

from nicegui import ui

from ..core.state import AppState
from .pages_data import UiState, build_data_page
from .pages_visualisation import build_visualisation_page


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
    with ui.tab_panels(tabs, value=data_tab).classes("w-full"):
        with ui.tab_panel(data_tab):
            build_data_page(holder)
            refreshers.append(holder.refresh)
        with ui.tab_panel(visualisation_tab):
            viz_refresh = build_visualisation_page(lambda: holder.state, set_state)
            refreshers.append(viz_refresh)

    holder.refresh = refresh_all


def main() -> None:
    ui.run(root=create_ui, host="127.0.0.1", port=8080, reload=False)


run_app = main
build_ui = create_ui
