from datetime import date
from pathlib import Path

from budget_gui_app.core.models import AppMetadata, CategoryStyle, Rule, Transaction
from budget_gui_app.core.state import AppState
from budget_gui_app.io.state_json import StateJsonRepository


def make_transaction(*, ignored: bool = True) -> Transaction:
    return Transaction(
        id=Transaction.make_id(date(2026, 5, 1), "card", "Migros", -10.0, "CHF"),
        date=date(2026, 5, 1),
        account="card",
        description="Migros",
        amount=-10.0,
        currency="CHF",
        source_file="sample.csv",
        category="Groceries",
        owner="shared",
        assignment_source="manual",
        ignored=ignored,
        edited=True,
    )


def make_state() -> AppState:
    return AppState(
        transactions=(make_transaction(),),
        rules=(Rule("r1", "migros", "Groceries", "shared", "outflow", 1),),
        category_styles=(CategoryStyle("Groceries", "#00ff00"),),
        metadata=AppMetadata(schema_version=1),
    )


def test_state_json_export_import_roundtrips_correctly(tmp_path: Path) -> None:
    state = make_state()
    path = tmp_path / "state.json"

    repository = StateJsonRepository()
    repository.save(state, path)
    loaded = repository.load(path)

    assert loaded == state


def test_exporting_profile_contains_rules_and_colours_but_no_transactions() -> None:
    profile = StateJsonRepository().to_profile_dict(make_state())

    assert "transactions" not in profile
    assert profile["rules"] == [
        {
            "id": "r1",
            "pattern": "migros",
            "category": "Groceries",
            "owner": "shared",
            "rule_type": "outflow",
            "transfer_sign_scope": "any",
            "priority": 1,
            "import_source": None,
        }
    ]
    assert profile["category_styles"] == [{"category": "Groceries", "colour": "#00ff00"}]
    assert profile["metadata"] == {"schema_version": 1}


def test_importing_profile_updates_rules_and_colours_without_changing_transactions() -> None:
    repository = StateJsonRepository()
    transaction = Transaction(
        id=Transaction.make_id(date(2026, 5, 2), "card", "Coop", -20.0, "CHF"),
        date=date(2026, 5, 2),
        account="card",
        description="Coop",
        amount=-20.0,
        currency="CHF",
    )
    state = AppState(transactions=(transaction,), rules=(Rule("old", "old", "Old", "Flo"),))
    profile = repository.to_profile_dict(
        AppState(
            rules=(Rule("new", "coop", "Groceries", "Shared", "outflow", 3),),
            category_styles=(CategoryStyle("Groceries", "#123456"),),
        )
    )

    updated = repository.apply_profile_dict(state, profile)

    assert updated.transactions[0].id == transaction.id
    assert updated.transactions[0].description == transaction.description
    assert updated.transactions[0].category == "Groceries"
    assert updated.transactions[0].assignment_source == "rule"
    assert updated.rules == (Rule("new", "coop", "Groceries", "Shared", "outflow", 3, None, "any"),)
    assert updated.category_styles == (CategoryStyle("Groceries", "#123456"),)


def test_full_backup_roundtrip_restores_transactions_rules_colours_ignored_flags_and_metadata() -> None:
    repository = StateJsonRepository()
    state = make_state()

    loaded = repository.from_dict(repository.to_dict(state))

    assert loaded == state
    assert loaded.transactions[0].ignored is True
    assert loaded.metadata.schema_version == 1


def test_old_state_without_cash_flow_type_loads_from_amount_sign() -> None:
    loaded = StateJsonRepository().from_dict(
        {
            "transactions": [
                {"id": "old-in", "date": "2026-05-01", "account": "card", "description": "Old in", "amount": "10", "currency": "CHF"},
                {"id": "old-out", "date": "2026-05-02", "account": "card", "description": "Old out", "amount": "-5", "currency": "CHF"},
            ]
        }
    )

    assert [transaction.flow_type for transaction in loaded.transactions] == ["inflow", "outflow"]


def test_old_state_without_category_colours_loads_and_invalid_colours_are_ignored() -> None:
    loaded = StateJsonRepository().from_dict(
        {
            "category_styles": {
                "Groceries": {"colour": None},
                "Rent": "not-a-colour",
                "Salary": "#123456",
            }
        }
    )

    assert loaded.category_styles == (CategoryStyle("Salary", "#123456"),)
