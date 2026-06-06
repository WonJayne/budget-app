from datetime import date

from budget_gui_app.core.models import CategoryStyle, Rule, Transaction
from budget_gui_app.core.periods import PeriodFilter, filter_transactions_by_period
from budget_gui_app.core.sankey import SankeyBuilder
from budget_gui_app.core.state import AppState
from budget_gui_app.core.summaries import yearly_overview
from budget_gui_app.io.state_json import StateJsonRepository


def tx(tx_id: str, tx_date: date, amount: float, category: str = "Groceries", owner: str = "Shared") -> Transaction:
    return Transaction(
        id=tx_id,
        date=tx_date,
        account="manual",
        description=tx_id,
        amount=amount,
        currency="CHF",
        category=category,
        owner=owner,
        assignment_source="manual",
        source_kind="manual",
    )


def test_period_filter_includes_only_matching_month_transactions() -> None:
    rows = (tx("may", date(2026, 5, 1), -10), tx("jun", date(2026, 6, 1), -20), tx("old", date(2025, 5, 1), -30))

    assert [row.id for row in filter_transactions_by_period(rows, PeriodFilter("month", 2026, 5))] == ["may"]


def test_period_filter_includes_all_matching_year_transactions() -> None:
    rows = (tx("may", date(2026, 5, 1), -10), tx("jun", date(2026, 6, 1), -20), tx("old", date(2025, 5, 1), -30))

    assert [row.id for row in filter_transactions_by_period(rows, PeriodFilter("year", 2026))] == ["may", "jun"]


def test_yearly_overview_aggregates_by_month_correctly() -> None:
    rows = (
        tx("salary", date(2026, 1, 1), 1000, "Salary"),
        tx("rent", date(2026, 1, 2), -700, "Rent"),
        tx("holiday", date(2026, 2, 2), -1200, "Holidays"),
    )

    overview = yearly_overview(rows, 2026)

    assert overview[0].total_inflow == 1000
    assert overview[0].total_outflow == 700
    assert overview[0].potential_savings == 300
    assert overview[1].deficit == 1200


def test_manual_entry_signs_edit_and_delete() -> None:
    state = AppState.empty()
    state = state.add_manual_transaction(flow_type="outflow", tx_date=date(2026, 1, 1), description="Rent", amount=500, currency="CHF", account="manual", category="Rent", owner="Shared")
    outflow_id = state.transactions[0].id
    state = state.add_manual_transaction(flow_type="inflow", tx_date=date(2026, 1, 2), description="Gift", amount=200, currency="CHF", account="manual", category="Gift", owner="Shared")

    assert state.transactions[0].amount == -500
    assert state.transactions[1].amount == 200

    state = state.update_manual_transaction(outflow_id, flow_type="inflow", tx_date=date(2026, 1, 3), description="Refund", amount=50, currency="CHF", account="manual", category="Refund", owner="Shared")
    assert next(row for row in state.transactions if row.id == outflow_id).amount == 50
    assert next(row for row in state.transactions if row.id == outflow_id).description == "Refund"

    state = state.remove_manual_transaction(outflow_id)
    assert all(row.id != outflow_id for row in state.transactions)


def test_rule_category_options_distinguish_inflows_and_outflows() -> None:
    state = AppState.empty().add_rule(Rule("salary-rule", "salary", "Salary", "Flo", "inflow")).add_rule(Rule("rent-rule", "rent", "Rent", "Shared", "outflow"))
    catalog = state.option_catalog()

    assert "Salary" in catalog.inflow_categories
    assert "Rent" in catalog.outflow_categories
    assert "Rent" not in catalog.inflow_categories


def test_colour_palette_assignment_persists_through_json_roundtrip() -> None:
    repository = StateJsonRepository()
    state = AppState.empty().set_category_colour("Groceries", "#4C78A8")

    loaded = repository.from_dict(repository.to_dict(state))

    assert loaded.category_style_map()["Groceries"] == CategoryStyle("Groceries", "#4C78A8")


def test_resetting_category_colour_removes_stored_custom_colour() -> None:
    state = AppState.empty().set_category_colour("Groceries", "#4C78A8")

    reset = state.set_category_colour("Groceries", None)

    assert "Groceries" not in reset.category_style_map()


def test_sankey_period_colours_never_include_none() -> None:
    rows = (tx("salary", date(2026, 1, 1), 1000, "Salary", "Flo"), tx("rent", date(2026, 1, 2), -700, "Rent", "Shared"))

    fig = SankeyBuilder().build(rows, {}, period=PeriodFilter("month", 2026, 1), include_ignored=False)

    assert None not in list(fig.data[0]["node"]["color"])
    assert None not in list(fig.data[0]["link"]["color"])
