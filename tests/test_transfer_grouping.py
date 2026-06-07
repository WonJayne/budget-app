from datetime import date

from budget_gui_app.core.models import Rule, Transaction
from budget_gui_app.core.periods import PeriodFilter
from budget_gui_app.core.sankey import SankeyBuilder
from budget_gui_app.core.state import AppState
from budget_gui_app.core.summaries import cash_flow_totals, included_transactions, transfer_monitor_totals, transfer_summary, yearly_overview
from budget_gui_app.io.state_json import StateJsonRepository


def transfer(tx_id: str, amount: float, group: str | None = None, note: str | None = None, tx_date: date = date(2026, 5, 1)) -> Transaction:
    return Transaction(
        id=tx_id,
        date=tx_date,
        account="account",
        description=tx_id,
        amount=amount,
        currency="CHF",
        cash_flow_type="transfer",
        category="Internal transfer",
        owner="Shared",
        assignment_source="manual",
        transfer_group_id=group,
        transfer_note=note,
    )


def budget_tx(tx_id: str, amount: float, tx_date: date = date(2026, 5, 1)) -> Transaction:
    return Transaction(
        id=tx_id,
        date=tx_date,
        account="account",
        description=tx_id,
        amount=amount,
        currency="CHF",
        category="Salary" if amount > 0 else "Rent",
        owner="Shared",
        assignment_source="manual",
    )


def test_main_sankey_excludes_transfers_even_when_toggle_flag_is_passed() -> None:
    rows = (transfer("out", -1350, "shared"), transfer("in", 1350, "shared"), budget_tx("salary", 2000))

    fig = SankeyBuilder().build(rows, {}, include_ignored=False, include_inflows=True, include_transfers=True)

    labels = list(fig.data[0]["node"]["label"])
    assert "Internal transfer" not in labels
    assert "shared" not in labels
    assert "Salary" in labels


def test_grouped_equal_transfer_sides_are_balanced_with_matched_amount() -> None:
    summary = transfer_summary((transfer("out", -1350, "cc"), transfer("in", 1350, "cc")))

    assert len(summary) == 1
    assert summary[0].status == "balanced"
    assert summary[0].matched_amount == 1350
    assert summary[0].unmatched_inflow == 0
    assert summary[0].unmatched_outflow == 0
    assert summary[0].net_movement == 0


def test_ungrouped_transfer_entries_are_reported_separately_as_single_sided() -> None:
    summary = transfer_summary((transfer("in", 500), transfer("out", -500)))

    assert [row.group_id for row in summary] == ["Ungrouped: in", "Ungrouped: out"]
    assert {row.status for row in summary} == {"single_sided"}


def test_partial_transfer_group_computes_unmatched_amounts() -> None:
    summary = transfer_summary((transfer("out", -1200, "cc"), transfer("in", 1500, "cc")))

    assert summary[0].status == "partial"
    assert summary[0].matched_amount == 1200
    assert summary[0].unmatched_inflow == 300
    assert summary[0].unmatched_outflow == 0
    assert summary[0].net_movement == 300
    assert summary[0].absolute_movement == 2700


def test_transfer_monitor_totals_sum_matched_unmatched_net_absolute_and_count() -> None:
    groups = transfer_summary(
        (
            transfer("out", -1200, "cc"),
            transfer("in", 1500, "cc"),
            transfer("single-out", -100, "savings"),
        )
    )

    totals = transfer_monitor_totals(groups)

    assert totals.matched_transfers == 1200
    assert totals.unmatched_transfer_inflow == 300
    assert totals.unmatched_transfer_outflow == 100
    assert totals.net_transfer_movement == 200
    assert totals.absolute_transfer_movement == 2800
    assert totals.transfer_count == 3


def test_monthly_and_yearly_budget_balances_ignore_transfers_but_report_monitor_columns() -> None:
    rows = (budget_tx("salary", 2000), budget_tx("rent", -700), transfer("out", -400, "save"), transfer("in", 400, "save"))

    included = included_transactions(rows, period=PeriodFilter("month", 2026, 5), include_inflows=True, include_ignored=False)
    totals = cash_flow_totals(included)
    overview = yearly_overview(rows, 2026)

    assert totals.total_inflow == 2000
    assert totals.total_outflow == 700
    assert totals.balance == 1300
    assert overview[4].balance == 1300
    assert overview[4].matched_transfers == 400
    assert overview[4].transfer_count == 2


def test_ledger_updates_preserve_transfer_group_and_note() -> None:
    state = AppState.empty().add_transactions((budget_tx("row", -100),))

    state = state.update_transaction(
        "row",
        flow_type="transfer",
        tx_date=date(2026, 5, 1),
        description="Card payment",
        amount=-100,
        currency="CHF",
        account="card",
        category="Credit card settlement",
        owner="Shared",
        ignored=False,
        transfer_group_id="cc-2026-05",
        transfer_note="credit card settlement",
    )

    edited = state.transactions[0]
    assert edited.id == "row"
    assert edited.transfer_group_id == "cc-2026-05"
    assert edited.transfer_note == "credit card settlement"


def test_full_backup_roundtrip_preserves_transfer_metadata_and_old_state_defaults_to_none() -> None:
    repository = StateJsonRepository()
    state = AppState(transactions=(transfer("out", -100, "g1", "note"),))

    loaded = repository.from_dict(repository.to_dict(state))
    old_loaded = repository.from_dict(
        {
            "transactions": [
                {
                    "id": "old",
                    "date": "2026-05-01",
                    "account": "account",
                    "description": "Old transfer",
                    "amount": "-100",
                    "currency": "CHF",
                    "cash_flow_type": "transfer",
                }
            ]
        }
    )

    assert loaded.transactions[0].transfer_group_id == "g1"
    assert loaded.transactions[0].transfer_note == "note"
    assert old_loaded.transactions[0].flow_type == "transfer"
    assert old_loaded.transactions[0].transfer_group_id is None
    assert old_loaded.transactions[0].transfer_note is None


def test_editing_transfer_rule_removes_stale_rule_based_transfer_classification() -> None:
    row = Transaction("Payment", date(2026, 5, 1), "account", "Payment", -100, "CHF")
    state = AppState(transactions=(row,)).add_rule(Rule("r1", "payment", "Internal transfer", "Shared", "transfer"))

    state = state.update_rule(Rule("r1", "no-match", "Internal transfer", "Shared", "transfer"))

    assert state.transactions[0].flow_type == "outflow"
    assert state.transactions[0].category is None
    assert state.transactions[0].assignment_source is None
