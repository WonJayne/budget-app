# AGENTS.md

This repository contains a local-only household budget application built in Python with NiceGUI.

Agents working on this repository must follow these instructions.

## Product Goal

The app should help a household import CSV bank/card exports, classify transactions, review unclear entries, add manual corrections, and visualise cash flow through a Sankey dashboard.

The intended mental model is:

```text
inflow category -> owner inflow -> Household pool -> owner outflow -> outflow category
```

Example:

```text
Salary -> Flo inflow -> Household pool
Salary -> Nina inflow -> Household pool
Gift -> Shared inflow -> Household pool
Household pool -> Shared outflow -> Groceries
Household pool -> Flo outflow -> Subscriptions
Household pool -> Nina outflow -> Personal care
```

Default owners are:

```text
Flo
Nina
Shared
```

## Local-Only Constraint

The app must remain local-only.

Allowed:

- running a NiceGUI server on `127.0.0.1`;
- importing local CSV files;
- exporting/importing local JSON state;
- using local Python dependencies from the project environment.

Not allowed:

- bank APIs;
- cloud sync;
- remote databases;
- user accounts;
- external analytics;
- external JavaScript CDNs for required functionality;
- background services outside the local app.

## Commands

Use `uv`.

Common commands:

```bash
uv sync
uv run budget-app
uv run pytest
```

Before finishing a code change, run:

```bash
uv run pytest
```

If possible, also verify startup:

```bash
uv run budget-app
```

## Architecture Rules

Keep the project compact and readable.

Preferred structure:

```text
src/budget_gui_app/
  app.py
  core/
    models.py
    state.py
    rules.py
    importers.py
    sankey.py
    summaries.py
  io/
    state_json.py
  ui/
    main.py
    pages_data.py
    pages_visualisation.py
```

Do not introduce a database unless explicitly requested.

Do not split code into many tiny files unless it clearly improves readability.

Core logic should be testable without starting NiceGUI.

## Core Data Principles

Use dataclasses and type hints throughout.

Prefer immutable core objects:

```python
@dataclass(frozen=True)
```

The UI may hold the current `AppState` in a small mutable holder because callbacks need to replace state.

Keep this mutation isolated in the UI layer.

## Transaction Semantics

Transaction sign determines flow type:

```text
amount > 0 -> inflow
amount < 0 -> outflow
amount == 0 -> neither / ignored by rules and Sankey
```

Use terminology:

```text
inflow
outflow
```

Avoid using only `income` and `expense` in core model names.

Imported CSV rows and manually created entries should be distinguishable, for example with:

```python
SourceKind = Literal["imported", "manual"]
```

Manual entries may be deleted.

Imported entries should normally be ignored/unignored rather than deleted.

## Rule Semantics

Rules must have a flow type:

```python
RuleType = Literal["inflow", "outflow"]
```

Rules match by case-insensitive substring in transaction descriptions.

Rules are applied in this order:

1. descending priority;
2. stable insertion order.

Rules must only apply to the matching transaction sign:

```text
inflow rule  -> positive transactions only
outflow rule -> negative transactions only
```

Manual assignments must not be overwritten by rules.

When rules are added, edited, or deleted, reapply rules so stale rule-based classifications disappear.

## Assignment Provenance

Preserve the distinction between manual and rule-based assignments.

Manual assignments survive rule reapplication.

Rule-based assignments can be removed or replaced when rules change.

Do not materialise rule effects in a way that leaves stale classifications after rule deletion.

## State Persistence

State export/import uses one JSON file.

The exported state should include at least:

- metadata/schema version;
- transactions;
- rules;
- category colours/styles.

Maintain backward compatibility where practical.

Old state files should not crash the app. Missing fields should get safe defaults.

When adding fields, update:

- JSON export;
- JSON import;
- examples;
- tests;
- README.

## UI Principles

The UI should be usable by non-developers.

Avoid raw text-only fields for values that are usually selected from known options.

For category, owner, currency, account, and rule type fields, prefer selectors.

Selectors should be populated from current state plus safe defaults.

Users must still be able to enter new values when needed.

A good pattern is:

```text
select known value OR choose "Other / new..." and type a new value
```

or any equivalent NiceGUI-native select/autocomplete behaviour.

## Option Catalog

Derive selectable values from state.

At minimum:

- owners: `Flo`, `Nina`, `Shared`, plus owners from transactions/rules;
- inflow categories: categories from positive transactions and inflow rules;
- outflow categories: categories from negative transactions and outflow rules;
- currencies: currencies from transactions plus `CHF`;
- accounts: accounts from transactions plus `manual`.

Flow-specific dialogs should show flow-specific category options.

## Required UI Areas

The app should have two main areas, tabs are fine.

### Data / Rules / Review

This area should support:

- CSV import;
- state import;
- state export;
- clear all data with confirmation;
- add/edit/delete inflow/outflow rules;
- review unclassified transactions;
- manually assign category/owner;
- create a reusable rule from a transaction;
- ignore/unignore transactions;
- add manual inflow entries;
- add manual outflow entries;
- delete manual entries.

### Visualisation

This area should support:

- month filter;
- owner filter;
- currency filter;
- include inflows toggle;
- include ignored toggle;
- embedded Plotly Sankey;
- category colour editor;
- total inflow/outflow/balance summary;
- category/owner summary table.

The Sankey should update inside the app. Do not open a temporary HTML file as the normal workflow.

## Sankey Semantics

Use this structure:

```text
inflow category -> owner inflow node -> Household pool -> owner outflow node -> outflow category
```

Balance logic:

```python
inflow_total = sum(tx.amount for tx in included if tx.amount > 0)
outflow_total = sum(abs(tx.amount) for tx in included if tx.amount < 0)
balance = inflow_total - outflow_total
```

If `balance > 0`, add:

```text
Household pool -> Potential savings
```

If `balance < 0`, add:

```text
Deficit -> Household pool
```

If `balance == 0`, add no balance node.

Do not create artificial transactions for balance nodes.

## Plotly Colour Rules

Do not pass `None` into Plotly colour lists.

Use valid fallback colours when no category colour is configured.

Category colours should be persisted in state and applied to category nodes where possible.

## Testing Requirements

Core logic needs pytest coverage.

When changing behaviour, update tests.

Important behaviours to test:

- CSV import;
- duplicate detection;
- inflow/outflow rule matching;
- rule priority;
- manual assignment preservation;
- stale rule removal;
- manual entry creation/deletion;
- Sankey household-pool structure;
- potential savings/deficit nodes;
- ignored transaction filtering;
- JSON roundtrip and migration defaults;
- option catalog defaults and derivation.

UI tests are not required unless explicitly requested.

## README Requirements

Keep the README accurate.

Do not claim unimplemented features.

README should explain:

- local-only operation;
- CSV format;
- inflows/outflows;
- default owners;
- rule editing;
- review workflow;
- manual entries;
- state import/export;
- run/test commands.

## Change Discipline

Prefer targeted refactors over full rewrites.

Do not break existing passing tests without replacing them with better tests.

Keep business logic in `core/`, not in UI callbacks.

After each meaningful change, think about:

- Does state export/import still work?
- Do rules reapply without stale assignments?
- Does manual assignment survive?
- Does the Sankey remain a derived view?
- Can a non-developer use the UI without typing everything manually?

## Completion Report

When finishing a task, report:

- changed files;
- tests run and result;
- manual verification performed;
- known limitations.

## UX and Period Model Rules

The app should feel like a household budget tool, not a raw database editor.

Use explicit period logic everywhere:

- All view;
- Year view;
- Month view.

Do not represent period selection as only a nullable month string.

Manual cash-flow entries must be editable and period-aware. They should be shown according to the current period filter.

Use select-or-create controls for user-facing fields such as owner, category, currency, and rule type. Plain text fields are acceptable for transaction descriptions and rule patterns.

Default owners are:

- Flo
- Nina
- Shared

Use the terms:

- inflow for positive cash movements;
- outflow for negative cash movements;
- Household pool as the central Sankey node;
- Potential savings for positive balance;
- Deficit for negative balance.

The colour editor must be human-friendly. Prefer a category dropdown plus palette chips. Raw hex editing may exist as an advanced option, but it must not be the primary workflow.

The visualisation page should always explain what period is shown. Monthly and yearly views must be clearly distinguishable.

The app should include a small How-to/Demo page explaining import, rules, manual entries, periods, balance, and state export/import.

Keep the app local-only. Do not introduce external services, bank APIs, cloud sync, user accounts, or CDN dependencies.

One extra product point: make Monthly the main/default view and Yearly the overview/reporting view. Most household finance decisions happen monthly; the yearly view is mainly for sanity checks like “are we actually saving over the year?”
