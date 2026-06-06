from datetime import date

from budget_gui_app.core.ledger import LedgerFilters, filter_ledger_transactions, transaction_entry_source
from budget_gui_app.core.models import Transaction
from budget_gui_app.core.periods import PeriodFilter
from budget_gui_app.core.state import AppState


def csv_tx(tx_id: str, tx_date: date, amount: float = -10, category: str | None = "Groceries", owner: str | None = "Shared", ignored: bool = False) -> Transaction:
    return Transaction(
        id=tx_id,
        date=tx_date,
        account="card",
        description=tx_id,
        amount=amount,
        currency="CHF",
        source_file="bank.csv",
        category=category,
        owner=owner,
        assignment_source="manual" if category or owner else None,
        ignored=ignored,
    )


def test_ledger_period_filtering_for_one_month() -> None:
    rows = (csv_tx("may", date(2026, 5, 3)), csv_tx("jun", date(2026, 6, 3)), csv_tx("old", date(2025, 5, 3)))

    filtered = filter_ledger_transactions(rows, LedgerFilters(period=PeriodFilter("month", 2026, 5)))

    assert [row.id for row in filtered] == ["may"]


def test_ledger_period_filtering_for_one_year() -> None:
    rows = (csv_tx("may", date(2026, 5, 3)), csv_tx("jun", date(2026, 6, 3)), csv_tx("old", date(2025, 5, 3)))

    filtered = filter_ledger_transactions(rows, LedgerFilters(period=PeriodFilter("year", 2026)))

    assert [row.id for row in filtered] == ["jun", "may"]


def test_ledger_includes_csv_and_manual_entries() -> None:
    state = AppState.empty().add_transactions((csv_tx("csv", date(2026, 5, 1)),))
    state = state.add_manual_transaction(flow_type="inflow", tx_date=date(2026, 5, 2), description="Gift", amount=50, currency="CHF", account="manual", category="Gift", owner="Shared")

    filtered = filter_ledger_transactions(state.transactions, LedgerFilters(period=PeriodFilter("month", 2026, 5)))

    assert {transaction_entry_source(row) for row in filtered} == {"csv", "manual"}


def test_editing_csv_imported_entry_keeps_original_id() -> None:
    state = AppState.empty().add_transactions((csv_tx("csv-id", date(2026, 5, 1)),))

    state = state.update_transaction("csv-id", flow_type="outflow", tx_date=date(2026, 5, 2), description="Edited", amount=20, currency="CHF", account="new-card", category="Rent", owner="Flo", ignored=False)

    edited = state.transactions[0]
    assert edited.id == "csv-id"
    assert edited.description == "Edited"
    assert edited.edited is True


def test_editing_outflow_with_positive_input_stores_negative_amount() -> None:
    state = AppState.empty().add_transactions((csv_tx("tx", date(2026, 5, 1), amount=-10),))

    state = state.update_transaction("tx", flow_type="outflow", tx_date=date(2026, 5, 1), description="Rent", amount=500, currency="CHF", account="card", category="Rent", owner="Shared", ignored=False)

    assert state.transactions[0].amount == -500


def test_editing_inflow_with_positive_input_stores_positive_amount() -> None:
    state = AppState.empty().add_transactions((csv_tx("tx", date(2026, 5, 1), amount=-10),))

    state = state.update_transaction("tx", flow_type="inflow", tx_date=date(2026, 5, 1), description="Refund", amount=500, currency="CHF", account="card", category="Refund", owner="Shared", ignored=False)

    assert state.transactions[0].amount == 500


def test_ignored_entries_can_be_included_in_ledger_via_filter() -> None:
    rows = (csv_tx("ignored", date(2026, 5, 1), ignored=True), csv_tx("active", date(2026, 5, 2)))

    filtered = filter_ledger_transactions(rows, LedgerFilters(period=PeriodFilter("month", 2026, 5), status="ignored"))

    assert [row.id for row in filtered] == ["ignored"]


def test_deleting_transaction_removes_it_from_state() -> None:
    state = AppState.empty().add_transactions((csv_tx("keep", date(2026, 5, 1)), csv_tx("delete", date(2026, 5, 2))))

    state = state.delete_transaction("delete")

    assert [row.id for row in state.transactions] == ["keep"]
