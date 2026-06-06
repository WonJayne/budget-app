from datetime import date

from budget_gui_app.core.models import Rule, Transaction
from budget_gui_app.core.sankey import DEFICIT_NODE, POOL_NODE, POTENTIAL_SAVINGS_NODE, SankeyBuilder
from budget_gui_app.core.state import AppState
from budget_gui_app.io.state_json import StateJsonRepository


def tx(description: str, amount: float, *, ignored: bool = False, category: str | None = None, owner: str | None = None, assignment_source=None) -> Transaction:
    return Transaction(
        id=Transaction.make_id(date(2026, 5, 1), "card", description, amount, "CHF"),
        date=date(2026, 5, 1),
        account="card",
        description=description,
        amount=amount,
        currency="CHF",
        category=category,
        owner=owner,
        assignment_source=assignment_source,
        ignored=ignored,
    )


def labels(state: AppState) -> list[str]:
    fig = SankeyBuilder().build(state.transactions, state.category_style_map(), month=None, owner=None, currency=None, include_inflows=True, include_ignored=False)
    return list(fig.data[0]["node"]["label"])


def test_inflow_rules_only_apply_to_positive_transactions() -> None:
    state = AppState.empty().add_transactions((tx("ACME payroll", 1000), tx("ACME refund paid out", -100)))
    state = state.add_rule(Rule("r1", "ACME", "Salary", "Flo", "inflow"))

    assert state.transactions[0].category == "Salary"
    assert state.transactions[0].owner == "Flo"
    assert state.transactions[1].category is None


def test_outflow_rules_only_apply_to_negative_transactions() -> None:
    state = AppState.empty().add_transactions((tx("Migros refund", 20), tx("Migros shop", -30)))
    state = state.add_rule(Rule("r1", "Migros", "Groceries", "Shared", "outflow"))

    assert state.transactions[0].category is None
    assert state.transactions[1].category == "Groceries"


def test_same_pattern_inflow_and_outflow_rules_do_not_cross_apply() -> None:
    state = AppState.empty().add_transactions((tx("Coop", 15), tx("Coop", -15)))
    state = state.add_rule(Rule("r1", "Coop", "Refund", "Shared", "inflow"))
    state = state.add_rule(Rule("r2", "Coop", "Groceries", "Shared", "outflow"))

    assert state.transactions[0].category == "Refund"
    assert state.transactions[1].category == "Groceries"


def test_rule_priority_is_respected_within_same_flow_type() -> None:
    state = AppState.empty().add_transactions((tx("Migros Zurich", -10),))
    state = state.add_rule(Rule("r1", "Migros", "Groceries", "Shared", "outflow", priority=0))
    state = state.add_rule(Rule("r2", "Migros", "Priority groceries", "Shared", "outflow", priority=10))

    assert state.transactions[0].category == "Priority groceries"


def test_manual_assignments_persist_after_inflow_outflow_rule_reapplication() -> None:
    state = AppState.empty().add_transactions((tx("ACME", 100), tx("Migros", -10)))
    state = state.manually_assign_transaction(state.transactions[0].id, "Manual inflow", "Nina")
    state = state.manually_assign_transaction(state.transactions[1].id, "Manual outflow", "Flo")
    state = state.add_rule(Rule("r1", "ACME", "Salary", "Flo", "inflow"))
    state = state.add_rule(Rule("r2", "Migros", "Groceries", "Shared", "outflow"))

    assert state.transactions[0].category == "Manual inflow"
    assert state.transactions[1].category == "Manual outflow"


def test_changing_or_deleting_inflow_rule_removes_stale_classification() -> None:
    state = AppState.empty().add_transactions((tx("ACME", 100),)).add_rule(Rule("r1", "ACME", "Salary", "Flo", "inflow"))
    assert state.transactions[0].category == "Salary"

    changed = state.update_rule(Rule("r1", "ACME", "Gift", "Shared", "inflow"))
    assert changed.transactions[0].category == "Gift"

    removed = changed.remove_rule("r1")
    assert removed.transactions[0].category is None
    assert removed.transactions[0].assignment_source is None


def test_changing_or_deleting_outflow_rule_removes_stale_classification() -> None:
    state = AppState.empty().add_transactions((tx("Migros", -10),)).add_rule(Rule("r1", "Migros", "Groceries", "Shared", "outflow"))
    assert state.transactions[0].category == "Groceries"

    changed = state.update_rule(Rule("r1", "Migros", "Food", "Shared", "outflow"))
    assert changed.transactions[0].category == "Food"

    removed = changed.remove_rule("r1")
    assert removed.transactions[0].category is None
    assert removed.transactions[0].assignment_source is None


def test_manual_inflow_and_outflow_entries_are_signed_and_removable() -> None:
    state = AppState.empty()
    state = state.add_manual_transaction(flow_type="inflow", tx_date=date(2026, 5, 1), description="Gift", amount=50, currency="CHF", account="manual", category="Gift", owner="Shared")
    state = state.add_manual_transaction(flow_type="outflow", tx_date=date(2026, 5, 2), description="Cash", amount=20, currency="CHF", account="manual", category="Cash", owner="Flo")

    assert state.transactions[0].amount == 50
    assert state.transactions[0].source_kind == "manual"
    assert state.transactions[0].assignment_source == "manual"
    assert state.transactions[1].amount == -20
    assert state.transactions[1].source_kind == "manual"

    removed = state.remove_manual_transaction(state.transactions[0].id)
    assert [transaction.description for transaction in removed.transactions] == ["Cash"]


def test_household_pool_sankey_balance_and_ignored_filtering() -> None:
    state = AppState.empty().add_transactions((
        tx("Salary", 100, category="Salary", owner="Flo", assignment_source="manual"),
        tx("Groceries", -40, category="Groceries", owner="Shared", assignment_source="manual"),
        tx("Ignored", -1000, ignored=True, category="Rent", owner="Shared", assignment_source="manual"),
    ))

    sankey_labels = labels(state)
    assert POOL_NODE in sankey_labels
    assert POTENTIAL_SAVINGS_NODE in sankey_labels
    assert "Rent" not in sankey_labels

    deficit_state = AppState.empty().add_transactions((tx("Salary", 10, category="Salary", owner="Flo", assignment_source="manual"), tx("Rent", -40, category="Rent", owner="Shared", assignment_source="manual")))
    assert DEFICIT_NODE in labels(deficit_state)


def test_json_roundtrip_preserves_rule_type_and_source_kind_and_old_json_loads() -> None:
    repo = StateJsonRepository()
    state = AppState.empty().add_manual_transaction(flow_type="inflow", tx_date=date(2026, 5, 1), description="Gift", amount=50, currency="CHF", account="manual", category="Gift", owner="Shared")
    state = state.add_rule(Rule("r1", "Gift", "Gift", "Shared", "inflow"))

    loaded = repo.from_dict(repo.to_dict(state))
    assert loaded.rules[0].rule_type == "inflow"
    assert loaded.transactions[0].source_kind == "manual"

    old = repo.from_dict({
        "transactions": [{"id": "old", "date": "2026-05-01", "account": "card", "description": "Migros", "amount": -10, "currency": "CHF"}],
        "rules": [{"id": "r-old", "pattern": "Migros", "category": "Groceries", "owner": "Shared"}],
    })
    assert old.transactions[0].source_kind == "manual"
    assert old.rules[0].rule_type == "outflow"


def test_option_catalog_defaults_and_derivation() -> None:
    state = AppState.empty().add_transactions((tx("Salary", 100, category="Salary", owner="Flo"), tx("Migros", -10, category="Groceries", owner="Nina")))
    state = state.add_rule(Rule("r1", "Gift", "Gift", "Shared", "inflow"))
    catalog = state.option_catalog()

    assert {"Flo", "Nina", "Shared"}.issubset(set(catalog.owners))
    assert {"Salary", "Gift"}.issubset(set(catalog.inflow_categories))
    assert "Groceries" in catalog.outflow_categories
    assert "CHF" in catalog.currencies
    assert "manual" in catalog.accounts
