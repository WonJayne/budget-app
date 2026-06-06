from datetime import date

from budget_gui_app.core.models import Rule, Transaction
from budget_gui_app.core.state import AppState


def make_tx() -> Transaction:
    return Transaction(
        id=Transaction.make_id(date(2026, 5, 1), "card", "Migros Wipkingen", -10.0, "CHF"),
        date=date(2026, 5, 1),
        account="card",
        description="Migros Wipkingen",
        amount=-10.0,
        currency="CHF",
    )


def test_deleting_or_changing_rule_does_not_leave_stale_classifications() -> None:
    state = AppState.empty().add_transactions((make_tx(),)).add_rule(Rule("r1", "migros", "Groceries", "shared"))
    assert state.transactions[0].category == "Groceries"

    changed = state.update_rule(Rule("r1", "migros", "Food", "shared"))
    assert changed.transactions[0].category == "Food"

    removed = changed.remove_rule("r1")
    assert removed.transactions[0].category is None
    assert removed.transactions[0].owner is None
    assert removed.transactions[0].assignment_source is None


def test_manual_assignment_persists_after_rule_reapplication() -> None:
    state = AppState.empty().add_transactions((make_tx(),))
    state = state.manually_assign_transaction(make_tx().id, "Manual", "me")
    state = state.add_rule(Rule("r1", "migros", "Groceries", "shared"))

    assert state.transactions[0].category == "Manual"
    assert state.transactions[0].owner == "me"
    assert state.transactions[0].assignment_source == "manual"


def test_clear_resets_data_but_keeps_metadata_valid() -> None:
    state = AppState.empty().add_transactions((make_tx(),)).add_rule(Rule("r1", "migros", "Groceries", "shared"))

    cleared = state.clear()

    assert cleared.transactions == ()
    assert cleared.rules == ()
    assert cleared.category_styles == ()
    assert cleared.metadata.schema_version == 1
