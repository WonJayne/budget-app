from pathlib import Path

from budget_gui_app.core.importers import TransactionImporter
from budget_gui_app.io.state_json import StateJsonRepository


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_sample_transactions_cover_multiple_months_accounts_and_categories() -> None:
    transactions = TransactionImporter().import_csv(EXAMPLES / "sample_transactions.csv")

    assert len(transactions) == 20
    assert {transaction.date.month for transaction in transactions} == {5, 6}
    assert {transaction.account for transaction in transactions} == {"shared_zkb", "flo_card", "nina_card"}
    assert sum(1 for transaction in transactions if transaction.amount > 0) == 5


def test_sample_state_loads_with_rich_rules_colours_and_classified_transactions() -> None:
    state = StateJsonRepository().load(EXAMPLES / "sample_state.json")

    assert len(state.transactions) == 20
    assert len(state.rules) >= 12
    assert len(state.category_styles) >= 10
    assert any(transaction.category == "Childcare" for transaction in state.transactions)
    assert any(transaction.owner == "Flo" for transaction in state.transactions)
    assert any(transaction.owner == "Nina" for transaction in state.transactions)
    assert all(transaction.category is not None for transaction in state.transactions[:-1])
    assert state.transactions[-1].description == "Running Shoes"
    assert state.transactions[-1].category is None
