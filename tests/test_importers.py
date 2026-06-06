from pathlib import Path

from budget_gui_app.core.importers import TransactionImporter
from budget_gui_app.core.state import AppState


def test_csv_importer_reads_valid_normalised_csv(tmp_path: Path) -> None:
    path = tmp_path / "transactions.csv"
    path.write_text("date,account,description,amount,currency,extra\n2026-05-01,card,Migros,-12.30,CHF,x\n", encoding="utf-8")

    transactions = TransactionImporter().import_csv(path)

    assert len(transactions) == 1
    assert transactions[0].account == "card"
    assert transactions[0].description == "Migros"
    assert transactions[0].amount == -12.30
    assert transactions[0].source_file == "transactions.csv"


def test_duplicate_transaction_import_skips_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "transactions.csv"
    path.write_text("date,account,description,amount,currency\n2026-05-01,card,Migros,-12.30,CHF\n", encoding="utf-8")
    transactions = TransactionImporter().import_csv(path)

    state = AppState.empty().add_transactions(transactions).add_transactions(transactions)

    assert len(state.transactions) == 1
