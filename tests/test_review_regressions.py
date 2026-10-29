from dataclasses import replace
from datetime import date

import pytest

from budget_gui_app.core.importers import TransactionImporter
from budget_gui_app.core.models import BudgetTarget, Rule, Transaction
from budget_gui_app.core.periods import PeriodFilter, entry_date_for_period
from budget_gui_app.core.state import AppState
from budget_gui_app.core.summaries import budget_comparison, cash_flow_totals, transfer_summary, yearly_overview
from budget_gui_app.io.state_json import StateJsonRepository


def tx(tx_id="t", amount=-100, **kwargs):
    return Transaction(tx_id, date(2026, 5, 1), "bank", "payment", amount, "CHF", **kwargs)


def test_append_deduplicates_existing_and_incoming_ids_in_order():
    original = tx("existing")
    first = tx("new")
    duplicate = replace(first, description="duplicate version")
    state, report = AppState(transactions=(original,)).import_transactions_append(iter((original, first, duplicate)))
    assert state.transactions == (original, first)
    assert report == {"added": 1, "skipped": 2, "replaced": 0, "missing": 0}


def test_add_transactions_deduplicates_one_batch_and_preserves_first_row():
    first = tx()
    state = AppState().add_transactions((first, replace(first, amount=-200)))
    assert state.transactions == (first,)


def test_append_classifies_only_new_rows_and_rule_changes_still_reclassify():
    rule = Rule("r", "payment", "Rent", "Shared")
    state = AppState(rules=(rule,)).add_transactions((tx("old"),))
    old = state.transactions[0]
    appended = state.add_transactions((tx("new"),))
    assert appended.transactions[0] is old
    assert appended.transactions[1].category == "Rent"
    updated = appended.update_rule(replace(rule, category="Other"))
    assert [row.category for row in updated.transactions] == ["Other", "Other"]
    assert all(row.category is None for row in updated.remove_rule("r").transactions)


def test_replace_deduplicates_input_and_counts_actually_missing_rows():
    kept = tx("other-source", import_source="other")
    current = tx("retained", import_source="feed")
    removed = tx("missing", import_source="feed")
    state = AppState(transactions=(kept, current, removed))
    result, report = state.import_transactions_replace_source_period((current, current, kept), "feed")
    assert result.transactions == (kept, current)
    assert report == {"added": 1, "skipped": 2, "replaced": 2, "missing": 1}


def test_manual_ids_do_not_repeat_after_deletion_and_roundtrip():
    kwargs = dict(flow_type="outflow", tx_date=date(2026, 5, 1), description="payment", amount=100,
                  currency="CHF", account="manual", category="Rent", owner="Shared")
    state = AppState()
    for _ in range(3):
        state = state.add_manual_transaction(**kwargs)
    old_ids = {row.id for row in state.transactions}
    state = state.delete_transaction(state.transactions[0].id).add_manual_transaction(**kwargs)
    assert len(state.transactions) == 3
    assert len({row.id for row in state.transactions}) == 3
    assert state.transactions[-1].id not in old_ids
    assert StateJsonRepository().from_dict(StateJsonRepository().to_dict(state)) == state


def test_cash_flow_totals_accepts_a_single_pass_generator():
    totals = cash_flow_totals(iter((tx("in", 100), tx("out", -50))))
    assert (totals.total_inflow, totals.total_outflow, totals.balance) == (100, 50, 50)


def test_yearly_overview_accepts_generator_and_filters_owner():
    rows = (tx("flo", 100, owner="Flo"), tx("nina", -30, owner="Nina"),
            replace(tx("june", -20, owner="Flo"), date=date(2026, 6, 1)))
    overview = yearly_overview(iter(rows), 2026, owner="Flo")
    assert overview[4].balance == 100
    assert overview[5].balance == -20


def test_budget_comparison_reuses_generator_for_all_targets():
    rows = (tx("in", 100, owner="Flo"), tx("out", -30, owner="Nina"))
    targets = (BudgetTarget("a", "Inflow", "inflow", None, None, "CHF", 100),
               BudgetTarget("b", "Outflow", "outflow", None, None, "CHF", 30))
    result = budget_comparison(iter(rows), targets, 2026, 5, "CHF", date(2026, 5, 31))
    assert [row.actual for row in result] == [100, 30]


def test_savings_target_respects_owner():
    rows = (tx("flo", 100, owner="Flo"), tx("nina", -30, owner="Nina"))
    target = BudgetTarget("s", "Flo savings", "savings", None, "Flo", "CHF", 100)
    result = budget_comparison(rows, (target,), 2026, 5, "CHF", date(2026, 5, 31))
    assert result[0].actual == 100


def test_ungrouped_transfers_with_shared_prefix_stay_separate():
    rows = (tx("abcdefgh1", -100, cash_flow_type="transfer"), tx("abcdefgh2", 100, cash_flow_type="transfer"))
    result = transfer_summary(rows)
    assert len(result) == 2
    assert all(row.status == "single_sided" and row.matched_amount == 0 for row in result)


def test_explicit_transfer_label_cannot_merge_with_generated_label():
    rows = (tx("abcdefgh1", -100, cash_flow_type="transfer"),
            tx("other", 100, cash_flow_type="transfer", transfer_group_id="Ungrouped: abcdefgh"))
    result = transfer_summary(rows)
    assert len(result) == 2
    assert all(row.matched_amount == 0 for row in result)


@pytest.mark.parametrize("period, expected", [
    (None, date(2026, 10, 29)),
    (PeriodFilter("all"), date(2026, 10, 29)),
    (PeriodFilter("year", 2025), date(2025, 1, 1)),
    (PeriodFilter("year", 2026), date(2026, 10, 29)),
    (PeriodFilter("month", 2025, 2), date(2025, 2, 1)),
])
def test_manual_entry_date_stays_in_selected_period(period, expected):
    assert entry_date_for_period(period, today=date(2026, 10, 29)) == expected


@pytest.mark.parametrize("pattern", ["", " ", "\t"])
def test_empty_rule_pattern_does_not_classify_every_transaction(pattern):
    state = AppState(rules=(Rule("r", pattern, "Rent", "Shared"),)).add_transactions((tx(),))
    assert state.transactions[0].category is None


def test_csv_upload_preserves_original_filename(tmp_path):
    path = tmp_path / "random-temporary.csv"
    path.write_text("date,account,description,amount,currency\n2026-05-01,bank,payment,-10,CHF\n")
    row, = TransactionImporter().import_csv(path, source_file="bank-statement.csv")
    assert row.source_file == "bank-statement.csv"
    assert row.import_source == "bank-statement"


@pytest.mark.parametrize("field, value", [
    ("amount", ""), ("amount", "inf"), ("amount", "-inf"), ("amount", "NaN"),
    ("date", ""), ("date", "invalid"), ("description", ""), ("currency", ""), ("account", ""),
])
def test_csv_rejects_invalid_rows_with_row_number(tmp_path, field, value):
    values = dict(date="2026-05-01", account="bank", description="payment", amount="-10", currency="CHF")
    values[field] = value
    path = tmp_path / "invalid.csv"
    path.write_text(",".join(values) + "\n" + ",".join(values.values()) + "\n")
    with pytest.raises(ValueError, match="CSV row 2:"):
        TransactionImporter().import_csv(path)
