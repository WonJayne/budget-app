from datetime import date

from budget_gui_app.core.models import Rule, Transaction
from budget_gui_app.ui.pages_data import (
    flow_label,
    flow_selection_for_transaction,
    flow_type_from_selection,
    rule_applicability_for_rule,
    rule_applicability_label,
    rule_applicability_to_model,
    signed_amount_from_flow_selection,
)


def tx(amount: float, cash_flow_type: str = "transfer") -> Transaction:
    return Transaction(
        id=f"tx-{amount}",
        date=date(2026, 5, 1),
        account="bank",
        description="Transfer",
        amount=amount,
        currency="CHF",
        cash_flow_type=cash_flow_type,
    )


def test_internal_transfer_in_selection_maps_to_transfer_and_positive_amount() -> None:
    assert flow_type_from_selection("transfer_in") == "transfer"
    assert signed_amount_from_flow_selection("transfer_in", 1350) == 1350


def test_internal_transfer_out_selection_maps_to_transfer_and_negative_amount() -> None:
    assert flow_type_from_selection("transfer_out") == "transfer"
    assert signed_amount_from_flow_selection("transfer_out", 1350) == -1350


def test_negative_typed_amount_is_normalised_for_internal_transfer_in() -> None:
    assert signed_amount_from_flow_selection("transfer_in", -1350) == 1350


def test_positive_typed_amount_is_normalised_for_internal_transfer_out() -> None:
    assert signed_amount_from_flow_selection("transfer_out", 1350) == -1350


def test_existing_positive_transfer_displays_as_internal_transfer_in() -> None:
    transaction = tx(1350)

    assert flow_selection_for_transaction(transaction) == "transfer_in"
    assert flow_label(transaction) == "Internal transfer in"


def test_existing_negative_transfer_displays_as_internal_transfer_out() -> None:
    transaction = tx(-1350)

    assert flow_selection_for_transaction(transaction) == "transfer_out"
    assert flow_label(transaction) == "Internal transfer out"


def test_rule_applicability_internal_transfer_in_maps_to_transfer_scope_in() -> None:
    assert rule_applicability_to_model("transfer_in") == ("transfer", "in")


def test_rule_applicability_internal_transfer_out_maps_to_transfer_scope_out() -> None:
    assert rule_applicability_to_model("transfer_out") == ("transfer", "out")


def test_rule_applicability_any_internal_transfer_maps_to_transfer_scope_any() -> None:
    assert rule_applicability_to_model("transfer_any") == ("transfer", "any")


def test_existing_transfer_rule_without_specific_scope_displays_any_internal_transfer() -> None:
    rule = Rule("r1", "transfer", "Internal transfer", "Shared", "transfer")

    assert rule_applicability_for_rule(rule) == "transfer_any"
    assert rule_applicability_label(rule) == "Any internal transfer"
