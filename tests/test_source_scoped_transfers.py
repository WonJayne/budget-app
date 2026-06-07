from datetime import date

from budget_gui_app.core.ledger import LedgerFilters, filter_ledger_transactions
from budget_gui_app.core.models import Rule, Transaction
from budget_gui_app.core.periods import PeriodFilter
from budget_gui_app.core.rules import RuleEngine
from budget_gui_app.core.sankey import SankeyBuilder
from budget_gui_app.core.state import AppState
from budget_gui_app.core.summaries import cash_flow_totals, included_transactions, transfer_summary
from budget_gui_app.io.state_json import StateJsonRepository


def tx(description: str = "Transfer", amount: float = -100.0, import_source: str = "ZKB private account") -> Transaction:
    return Transaction(
        id=Transaction.make_id(date(2026, 5, 1), import_source, description, amount, "CHF"),
        date=date(2026, 5, 1),
        account=import_source,
        description=description,
        amount=amount,
        currency="CHF",
        source_file=f"{import_source}.csv",
        import_source=import_source,
    )


def test_global_rule_applies_to_all_sources() -> None:
    rule = Rule("r1", "transfer", "Miscellaneous", "Shared", "outflow")

    classified = RuleEngine((rule,)).classify_many((tx(import_source="A"), tx(import_source="B")))

    assert [row.category for row in classified] == ["Miscellaneous", "Miscellaneous"]


def test_source_scoped_rule_applies_only_to_matching_import_source() -> None:
    rule = Rule("r1", "transfer", "Internal transfer", "Flo", "transfer", import_source="ZKB private account")

    matching, other = RuleEngine((rule,)).classify_many((tx(import_source="ZKB private account"), tx(import_source="ZKB shared account")))

    assert matching.flow_type == "transfer"
    assert matching.category == "Internal transfer"
    assert other.category is None


def test_source_specific_rule_wins_over_global_rule_with_equal_priority() -> None:
    rules = (
        Rule("global", "transfer", "Miscellaneous", "Shared", "outflow", priority=0),
        Rule("specific", "transfer", "Internal transfer", "Flo", "transfer", priority=0, import_source="ZKB private account"),
    )

    classified = RuleEngine(rules).classify(tx(import_source="ZKB private account"))

    assert classified.flow_type == "transfer"
    assert classified.category == "Internal transfer"


def test_rule_source_scope_survives_state_json_and_profile_roundtrip() -> None:
    repository = StateJsonRepository()
    state = AppState(rules=(Rule("r1", "transfer", "Internal transfer", "Flo", "transfer", 7, "ZKB private account"),))

    loaded_state = repository.from_dict(repository.to_dict(state))
    profile_state = repository.apply_profile_dict(AppState(), repository.to_profile_dict(state))

    assert loaded_state.rules == state.rules
    assert profile_state.rules == state.rules


def test_old_state_without_import_source_still_loads() -> None:
    loaded = StateJsonRepository().from_dict(
        {
            "transactions": [
                {
                    "id": "old",
                    "date": "2026-05-01",
                    "account": "card",
                    "description": "Old row",
                    "amount": "10.0",
                    "currency": "CHF",
                    "source_file": "/tmp/old-feed.csv",
                }
            ]
        }
    )

    assert loaded.transactions[0].stable_import_source == "old-feed"
    assert loaded.transactions[0].flow_type == "inflow"


def test_transfer_rule_applies_to_positive_and_negative_transactions() -> None:
    rule = Rule("r1", "payment", "Credit card settlement", "Shared", "transfer")

    positive, negative = RuleEngine((rule,)).classify_many((tx("Payment", 100.0), tx("Payment", -100.0)))

    assert positive.flow_type == "transfer"
    assert negative.flow_type == "transfer"


def test_transfer_transactions_are_excluded_from_totals_and_sankey_by_default() -> None:
    transfer = tx("Payment", -100.0)
    transfer = Transaction(**{**transfer.__dict__, "cash_flow_type": "transfer", "category": "Internal transfer", "owner": "Shared"})

    included = included_transactions((transfer,), include_inflows=True, include_ignored=False)
    totals = cash_flow_totals((transfer,))
    fig = SankeyBuilder().build((transfer,), {}, include_ignored=False, include_inflows=True)

    assert included == ()
    assert totals.total_inflow == 0
    assert totals.total_outflow == 0
    assert totals.balance == 0
    assert fig.data[0]["node"]["label"] == ()


def test_transfer_transactions_are_visible_in_ledger_filter() -> None:
    transfer = Transaction(**{**tx().__dict__, "cash_flow_type": "transfer", "category": "Internal transfer", "owner": "Shared"})

    rows = filter_ledger_transactions((transfer,), LedgerFilters(period=PeriodFilter("all"), flow_type="transfer"))

    assert rows == (transfer,)


def test_manual_transfer_assignment_persists_through_rule_reapplication() -> None:
    state = AppState(transactions=(tx("Transfer"),), rules=(Rule("r1", "transfer", "Expense", "Shared", "outflow"),))
    state = state.manually_assign_transaction(state.transactions[0].id, "Internal transfer", "Flo", "transfer")

    reapplied = state.reapply_rules()

    assert reapplied.transactions[0].flow_type == "transfer"
    assert reapplied.transactions[0].category == "Internal transfer"
    assert reapplied.transactions[0].assignment_source == "manual"


def test_deleting_transfer_rule_removes_stale_rule_based_transfer_classification() -> None:
    state = AppState(transactions=(tx("Payment"),)).add_rule(Rule("r1", "payment", "Internal transfer", "Shared", "transfer"))

    updated = state.remove_rule("r1")

    assert updated.transactions[0].flow_type == "outflow"
    assert updated.transactions[0].category is None
    assert updated.transactions[0].assignment_source is None


def test_transfer_summary_computes_transfer_monitor_values() -> None:
    rows = (
        Transaction(**{**tx(amount=1500.0).__dict__, "cash_flow_type": "transfer", "category": "Credit card settlement", "owner": "Shared"}),
        Transaction(**{**tx(amount=-1200.0).__dict__, "cash_flow_type": "transfer", "category": "Credit card settlement", "owner": "Shared"}),
    )

    summary = transfer_summary(rows)

    assert summary[0].category == "Credit card settlement"
    assert summary[0].count == 2
    assert summary[0].transfer_inflow == 1500
    assert summary[0].transfer_outflow == 1200
    assert summary[0].net_movement == 300
    assert summary[0].absolute_movement == 2700


def test_showing_transfers_does_not_add_them_to_main_sankey() -> None:
    transfer = Transaction(**{**tx(amount=-50.0).__dict__, "cash_flow_type": "transfer", "category": "Savings transfer", "owner": "Shared"})

    fig = SankeyBuilder().build((transfer,), {}, include_ignored=False, include_inflows=True, include_transfers=True)

    assert "Internal transfers" not in fig.data[0]["node"]["label"]
    assert "Savings transfer" not in fig.data[0]["node"]["label"]
    assert "Household pool" not in fig.data[0]["node"]["label"]
