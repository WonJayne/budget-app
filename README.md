# Budget GUI App

A local-only household cash-flow dashboard built with Python, NiceGUI, pandas, and Plotly. It imports normalized CSV transaction exports, classifies inflows and outflows with editable rules, supports manual corrections, persists state as JSON, and visualises household cash flow with an embedded Sankey diagram.

The app runs on `127.0.0.1` and intentionally has no cloud sync, user accounts, bank APIs, remote database, or external analytics.

## Install, run, and test

```bash
uv sync
uv run budget-app
uv run pytest
```

Open the local NiceGUI page shown in the terminal, normally <http://127.0.0.1:8080>.

## CSV format

The importer supports normalized CSV files with these required columns:

```csv
date,account,description,amount,currency
2026-05-01,shared_zkb,Salary Flo,5000.00,CHF
2026-05-03,shared_zkb,Migros Wipkingen,-84.30,CHF
```

Additional columns are ignored. Transaction IDs are deterministic from the raw transaction fields, so duplicate imports are skipped.

## Cash-flow model

Transaction sign determines the flow type:

- `amount > 0` is an **inflow** such as salary, gifts, reimbursements, refunds, or corrections.
- `amount < 0` is an **outflow** such as groceries, rent, subscriptions, personal spending, savings transfers, or corrections.
- `amount == 0` is ignored by rules and the Sankey.

Default household owners are `Flo`, `Nina`, and `Shared`. The UI derives selector options from the current state while still allowing new categories, owners, accounts, and currencies where needed.

## Data, rules, and review workflow

The **Data / Rules / Review** tab supports:

- CSV import;
- JSON state import/export;
- clearing the current local state with confirmation;
- adding manual inflow and outflow entries;
- deleting manual entries;
- adding, editing, and deleting inflow/outflow rules;
- reviewing unclassified imported transactions;
- manually assigning category/owner for a single transaction;
- creating a reusable rule from a reviewed transaction;
- ignoring transactions that should not be classified.

Rules are case-insensitive description substring matches. Each rule has a visible `inflow` or `outflow` type, so inflow rules apply only to positive transactions and outflow rules apply only to negative transactions. Rule priority is respected, and manual assignments survive rule reapplication. Editing or deleting rules removes stale rule-based classifications.

Manual entries are stored as local transactions with `source_kind="manual"`, no source file, and manual assignment provenance. Inflow entries are stored as positive amounts; outflow entries are stored as negative amounts.

## Visualisation

The **Visualisation** tab includes filters for month, owner, currency, inflows, and ignored transactions. It renders an embedded Plotly Sankey using this household-pool structure:

```text
inflow category -> owner inflow -> Household pool -> owner outflow -> outflow category
```

When inflows exceed outflows, the Sankey shows `Household pool -> Potential savings`. When outflows exceed inflows, it shows `Deficit -> Household pool`.

The page also shows summary cards for total inflow, total outflow, balance, potential savings, and deficit, plus a category/owner summary table that distinguishes inflows from outflows.

## State import/export

State export/import uses one local JSON file containing schema metadata, transactions, rules, and category colours. Exporting state materialises the current app state, including manual entries, rule types, assignment provenance, ignored flags, and category colour settings.

Older state files with missing fields are loaded with safe defaults where practical; for example, old rules without `rule_type` default to `outflow`, and old transactions without `source_kind` default to `imported`.

## Examples

- `examples/sample_transactions.csv` contains a normalized CSV sample with Flo, Nina, and Shared inflows/outflows.
- `examples/sample_state.json` contains a state export sample with inflow/outflow rules, category colours, classified transactions, and one unclassified transaction for review.
