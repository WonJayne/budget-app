# Budget GUI App

A local-only household budget prototype for importing normalized CSV transaction exports, classifying them with rules, reviewing unclassified entries, persisting state as JSON, and visualising the current budget with an embedded Plotly Sankey dashboard in NiceGUI.

The application runs on `127.0.0.1` and does not implement cloud sync, user accounts, bank APIs, or external-server workflows.

## Install and run

```bash
uv sync
uv run budget-app
```

Open the local NiceGUI page shown in the terminal, normally <http://127.0.0.1:8080>.

## CSV format

The initial importer supports normalized CSV files with these required columns:

```csv
date,account,description,amount,currency
2026-05-02,shared_zkb,Migros Wipkingen,-84.30,CHF
```

Additional columns are ignored. Transaction IDs are deterministic and duplicate imports are skipped by ID.

## Features implemented

- Additive CSV import with duplicate skipping.
- Rule-based classification using case-insensitive description substring matching.
- Rule priority with stable insertion-order tie breaking.
- Manual transaction assignment that survives rule changes.
- Rule reapplication that removes stale rule-derived classifications after rule edits/deletes.
- Review queue for unclassified transactions, with assign, create-rule, and ignore actions.
- JSON state import/export for transactions, rules, category colours, and schema metadata.
- Embedded dynamic Sankey visualisation with month, owner, currency, income, and ignored filters.
- Category colour editing persisted in exported state.

## Tests

```bash
uv run pytest
```

## Examples

- `examples/sample_transactions.csv` contains a small normalized CSV import sample.
- `examples/sample_state.json` contains a small state export sample.

## Preliminary PyInstaller packaging note

NiceGUI applications can require hidden imports and static assets depending on the target platform. A first exploratory command is:

```bash
uv add --dev pyinstaller
uv run pyinstaller --name budget-app --onefile src/budget_gui_app/app.py
```

If the generated executable does not include all NiceGUI assets, use PyInstaller's collected-data options for `nicegui` and `plotly`, or switch to a one-folder build while validating packaging.
