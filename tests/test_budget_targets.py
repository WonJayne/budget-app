from datetime import date

from budget_gui_app.core.models import BudgetTarget, Transaction
from budget_gui_app.core.summaries import budget_comparison, budget_plan_totals, project_month_end
from budget_gui_app.core.state import AppState
from budget_gui_app.io.state_json import StateJsonRepository


def tx(tx_id: str, amount: float, category: str, owner: str = "Shared", ignored: bool = False, flow: str | None = None) -> Transaction:
    return Transaction(tx_id, date(2026, 5, 10), "account", tx_id, amount, "CHF", category=category, owner=owner, ignored=ignored, cash_flow_type=flow)


def test_budget_target_json_roundtrip_and_inactive_excluded() -> None:
    targets = (
        BudgetTarget("b1", "Groceries", "outflow", "Groceries", "Shared", "CHF", 800),
        BudgetTarget("b2", "Old", "outflow", None, None, "CHF", 999, active=False),
    )
    state = AppState(budget_targets=targets)
    loaded = StateJsonRepository().from_dict(StateJsonRepository().to_dict(state))

    totals = budget_plan_totals((), loaded.budget_targets, 2026, 5, "CHF", date(2026, 5, 31))

    assert loaded.budget_targets == targets
    assert totals.planned_outflow == 800


def test_monthly_actuals_exclude_transfers_and_ignored_transactions() -> None:
    rows = (
        tx("salary", 5000, "Salary"),
        tx("rent", -2000, "Rent"),
        tx("ignored", -100, "Rent", ignored=True),
        tx("transfer", -500, "Internal transfer", flow="transfer"),
    )
    totals = budget_plan_totals(rows, (), 2026, 5, "CHF", date(2026, 5, 31))

    assert totals.actual_inflow == 5000
    assert totals.actual_outflow == 2000
    assert totals.actual_savings == 3000


def test_budget_comparison_differences_for_outflow_inflow_and_savings() -> None:
    rows = (tx("salary", 5000, "Salary", "Flo"), tx("groceries", -700, "Groceries", "Shared"))
    targets = (
        BudgetTarget("out", "Groceries", "outflow", "Groceries", "Shared", "CHF", 800),
        BudgetTarget("in", "Salary", "inflow", "Salary", "Flo", "CHF", 4500),
        BudgetTarget("save", "Savings", "savings", None, None, "CHF", 3000),
    )
    rows_out = budget_comparison(rows, targets, 2026, 5, "CHF", date(2026, 5, 31))

    assert rows_out[0].difference == 100
    assert rows_out[1].difference == 500
    assert rows_out[2].actual == 4300
    assert rows_out[2].difference == 1300


def test_projection_historical_equals_actual_and_current_uses_progress() -> None:
    assert project_month_end(300, 2026, 4, date(2026, 5, 15)) == 300
    assert project_month_end(300, 2026, 5, date(2026, 5, 15)) == 620
