from datetime import date

from budget_gui_app.core.models import Rule, Transaction
from budget_gui_app.core.rules import RuleEngine


def tx(description: str = "MIGROS WIPKINGEN") -> Transaction:
    return Transaction(
        id=Transaction.make_id(date(2026, 5, 1), "card", description, -10.0, "CHF"),
        date=date(2026, 5, 1),
        account="card",
        description=description,
        amount=-10.0,
        currency="CHF",
    )


def test_rule_matching_is_case_insensitive() -> None:
    classified = RuleEngine((Rule("r1", "migros", "Groceries", "shared"),)).classify(tx())

    assert classified.category == "Groceries"
    assert classified.owner == "shared"
    assert classified.assignment_source == "rule"


def test_rule_priority_is_respected() -> None:
    rules = (Rule("low", "migros", "Low", "shared", priority=0), Rule("high", "migros", "High", "shared", priority=10))

    assert RuleEngine(rules).classify(tx()).category == "High"


def test_rule_classification_does_not_overwrite_manual_assignments() -> None:
    manual = tx()
    manual = Transaction(**{**manual.__dict__, "category": "Manual", "owner": "me", "assignment_source": "manual"})

    classified = RuleEngine((Rule("r1", "migros", "Groceries", "shared"),)).classify(manual)

    assert classified.category == "Manual"
    assert classified.owner == "me"
    assert classified.assignment_source == "manual"
