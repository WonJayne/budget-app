# Budget GUI Application

This project implements a local‑only Python application for analysing
household finances from bank or credit‑card exports.  The design
supports importing transactions, maintaining a set of classification
rules, reviewing and correcting unclassified transactions, saving and
loading state, and visualising the current budget as a Sankey
diagram.  The application runs as a desktop program using Python’s
standard `tkinter` library for the user interface and embeds
Matplotlib for plotting.

## Features

* **CSV import**: Read one or more CSV files in normalised format
  (`date,account,description,amount,currency`).  Duplicate
  transactions are automatically detected and skipped.
* **Rule engine**: Define simple substring matching rules to assign
  categories and owners to transactions.  Rules are evaluated by
  priority and insertion order.
* **Review workflow**: Inspect transactions that remain
  unclassified and assign categories/owners manually or derive new
  rules from them.  Ignored transactions do not appear in the
  Sankey diagram.
* **State persistence**: Export and import the complete application
  state to/from a JSON file.  Clearing the state resets all
  transactions, rules and category styles.
* **Dynamic Sankey visualisation**: Generate a Plotly Sankey
  diagram on demand based on the current state and simple filters
  (month, owner).  The diagram is saved as a temporary HTML file and
  opened in your default web browser for interactive exploration.
* **Category colours**: Assign custom colours to categories via a
  colour chooser; these are persisted as part of the application
  state and used in the Sankey.

## Requirements

The project targets Python 3.10 or later and uses only standard
library modules plus `pandas`, `plotly` and `matplotlib`.  These
dependencies are declared in `pyproject.toml`.  The graphical user
interface relies on `tkinter`, which is included in most Python
distributions.

## Running the application

Using **Poetry** (recommended for development):

```bash
poetry install
poetry run budget-gui-app
```

Using **uv** (lightweight dependency manager):

```bash
uv pip install -r requirements.txt  # generate requirements with `poetry export -f requirements.txt --output requirements.txt`
uv run python -m budget_gui_app.ui.main
```

### Packaging as an executable

Once dependencies are installed you can build a standalone executable
using a tool such as PyInstaller:

```bash
pyinstaller --name budget-gui-app --onefile src/budget_gui_app/ui/main.py
```

The resulting binary will run without requiring Python to be
installed.  Note that PyInstaller must be installed in your
environment.  Adjust paths as necessary based on your setup.

## Directory layout

```
budget_gui_app/
  pyproject.toml       Poetry configuration
  README.md            This file
  src/
    budget_gui_app/
      __init__.py
      core/
        models.py        Data models (transactions, rules, styles)
        state.py         Application state and update operations
        rules.py         Rule engine for classification
        importers.py     CSV import logic
        sankey.py        Sankey construction using Plotly
      io/
        state_json.py    JSON import/export for AppState
      ui/
        main.py          Tkinter UI entry point
    examples/
      sample_transactions.csv   Example CSV input
      sample_state.json         Example exported state
```

## Notes

This prototype focuses on correctness and clarity rather than visual
polish.  It uses Tkinter for portability and avoids external
web‑framework dependencies because the project is intended to run
offline.  You can adapt the GUI layer to another framework (such as
NiceGUI or Streamlit) in the future if those dependencies become
available.