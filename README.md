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

- **Import transactions CSV** to append/update the transaction ledger only;
- **Export ledger CSV** for the transaction ledger only;
- **Import full backup** / **Export full backup** for complete JSON state;
- **Import rules/profile** / **Export rules/profile** for rules, category colours, default options, and metadata without transaction data;
- **Clear transactions** to remove ledger/manual entries while keeping rules/profile;
- **Clear all data** to remove transactions, rules, colours, and reset metadata;
- an **All entries** ledger for CSV-imported and manual entries;
- ledger filtering by All/Year/Month period, source, flow type, owner, category, and status;
- editing imported CSV entries without changing their stable transaction IDs;
- ignoring/unignoring duplicate or unwanted imported entries while keeping them traceable;
- deleting entries, with imported entries intended to be ignored first when possible;
- adding manual inflow and outflow entries in the selected All/Year/Month period;
- editing and deleting manual entries;
- adding, editing, and deleting inflow/outflow rules;
- reviewing unclassified imported transactions;
- manually assigning category/owner for a single transaction;
- creating a reusable rule from a reviewed transaction;
- ignoring transactions that should not be classified.

Rules are case-insensitive description substring matches. Each rule has a visible `inflow` or `outflow` type, so inflow rules apply only to positive transactions and outflow rules apply only to negative transactions. Rule priority is respected, and manual assignments survive rule reapplication. Editing or deleting rules removes stale rule-based classifications.

The **All entries** ledger is the main source-of-truth view for the cash-flow data that creates the Sankey. It shows date, source (`csv` or `manual`), account, flow type, description, amount, currency, category, owner, assignment source, ignored status, and row actions. The same explicit period model used by the rest of the app applies to the ledger: **All** shows every entry, **Year** shows the selected year, and **Month** shows only the selected month.

Imported CSV entries can be edited in the ledger when a bank export needs correction. Editing preserves the original transaction ID so duplicate detection and saved state stay consistent. The edit dialog lets users change date, flow type, description, amount, currency, account, category, owner, and ignored status. Users can type positive amounts for both inflows and outflows; the selected flow type normalises storage so inflows remain positive and outflows remain negative.

For duplicate CSV rows or unwanted imported entries, use **Ignore** whenever possible. Ignored entries remain visible through the ledger status filter, can be unignored later, and are excluded from Sankey and summaries by default.

Manual entries are stored as local transactions with `source_kind="manual"`/`entry_source="manual"`, no source file, and manual assignment provenance. Inflow entries are stored as positive amounts; outflow entries are stored as negative amounts. Manual entries can be added from the existing manual-entry controls and edited later through the same ledger edit dialog.

## Visualisation

The **Visualisation** tab includes an explicit period selector for **All**, **Year**, and **Month** views, plus owner, currency, inflow, and ignored-transaction filters. Monthly view is the default so day-to-day household decisions focus on one budget month; yearly view is used for overview/reporting. It renders an embedded Plotly Sankey using this household-pool structure:

```text
inflow category -> owner inflow -> Household pool -> owner outflow -> outflow category
```

When inflows exceed outflows, the Sankey shows `Household pool -> Potential savings`. When outflows exceed inflows, it shows `Deficit -> Household pool`.

The page also shows summary cards for total inflow, total outflow, balance, potential savings, and deficit. Tabs provide the Sankey, a yearly overview table aggregated by month, and a category/owner summary table that distinguishes inflows from outflows.

## Category colours

Category colours are edited with a compact dropdown, a large current-colour preview, and visible palette chips that show their actual colours. Pick a category, click a palette chip, then save the colour. A native colour picker and custom hex input are available under an advanced section, but normal use does not require typing hex codes. **Reset to automatic** removes the stored custom colour so the Sankey uses safe fallback colours. Saved category colours are included in full-backup and rules/profile JSON export/import and reapplied to Sankey category nodes where possible.

## How-to and demo

The **How it works** tab explains CSV import, manual entries, inflow/outflow rules, monthly and yearly filtering, the Household pool, Potential savings/Deficit, and full-backup and rules/profile import/export. The **Load demo data** button replaces the current data after confirmation and loads two months of Flo/Nina/Shared example transactions with one savings month and one deficit month.

## Import/export and backups

The app separates transaction data, reusable profile settings, and full backups:

- **Import transactions CSV** appends new CSV transactions to the current ledger and skips duplicate transaction IDs. It keeps existing rules, colours, metadata, manual edits, and ignored flags.
- **Export ledger CSV** exports the transaction ledger only for spreadsheet use.
- **Export full backup** writes a local JSON file containing complete app state: schema metadata, profile options, transactions, manual entries, edited ledger fields, ignored flags, assignment provenance, rules, and category colours.
- **Import full backup** replaces the complete current app state with the JSON backup.
- **Export rules/profile** writes JSON containing schema metadata, derived/default selector options, rules, and category colours, with no transaction ledger data.
- **Import rules/profile** updates rules, colours, profile options, and metadata while keeping the existing transaction ledger. Rules are reapplied so rule-based classifications match the imported profile.
- **Clear transactions** removes imported and manual ledger entries while keeping rules, colours, profile options, and metadata.
- **Clear all data** resets the local app to an empty state, removing transactions, rules, colours, profile options, and metadata customisations.

Older full-backup files with missing fields are loaded with safe defaults where practical; for example, old rules without `rule_type` default to `outflow`, and old transactions without `source_kind` infer manual entries when `source_file` is missing or `manual`.

## Examples

- `examples/sample_transactions.csv` contains a normalized CSV sample with Flo, Nina, and Shared inflows/outflows.
- `examples/sample_state.json` contains a state export sample with inflow/outflow rules, category colours, classified transactions, and one unclassified transaction for review.
