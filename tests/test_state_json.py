from datetime import date
from pathlib import Path

from budget_gui_app.core.models import CategoryStyle, Rule, Transaction
from budget_gui_app.core.state import AppState
from budget_gui_app.io.state_json import StateJsonRepository


def test_state_json_export_import_roundtrips_correctly(tmp_path: Path) -> None:
    transaction = Transaction(
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
        ignored=True,
    )
    state = AppState(
        transactions=(transaction,),
        rules=(Rule("r1", "migros", "Groceries", "shared", 1),),
        category_styles=(CategoryStyle("Groceries", "#00ff00"),),
    )
    path = tmp_path / "state.json"

    repository = StateJsonRepository()
    repository.save(state, path)
    loaded = repository.load(path)

    assert loaded == state
