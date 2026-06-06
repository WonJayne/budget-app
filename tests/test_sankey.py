from datetime import date

from budget_gui_app.core.models import CategoryStyle, Transaction
from budget_gui_app.core.sankey import SankeyBuilder


def make_tx(ignored: bool = False) -> Transaction:
    return Transaction(
        id=Transaction.make_id(date(2026, 5, 1), "card", "Migros", -10.0, "CHF"),
        date=date(2026, 5, 1),
        account="card",
        description="Migros",
        amount=-10.0,
        currency="CHF",
        category="Groceries",
        owner="shared",
        assignment_source="manual",
        ignored=ignored,
    )


def test_ignored_transactions_are_excluded_from_sankey_by_default() -> None:
    fig = SankeyBuilder().build((make_tx(ignored=True),), {}, month=None, owner=None, currency=None, include_income=True, include_ignored=False)

    assert fig.data[0]["node"]["label"] == ()
    assert fig.data[0]["link"]["value"] == ()


def test_category_colours_are_applied_without_none_colour_lists() -> None:
    fig = SankeyBuilder().build(
        (make_tx(),),
        {"Groceries": CategoryStyle("Groceries", "#00ff00")},
        month=None,
        owner=None,
        currency=None,
        include_income=True,
        include_ignored=False,
    )

    node_colours = list(fig.data[0]["node"]["color"])
    link_colours = list(fig.data[0]["link"]["color"])
    assert "#00ff00" in node_colours
    assert None not in node_colours
    assert None not in link_colours
