# Budget App Agenda and Target State

## Purpose

This document defines the target state for the local household budget application and records the main gaps in the current prototype. It should be used as the implementation agenda for the next development pass.

The desired product is a **local-only, dynamic budget dashboard** for importing CSV bank/card exports, classifying transactions, reviewing unresolved entries, and visualising household cash flow through an interactive Sankey diagram.

The Sankey diagram is a **view of the current transaction state**, not the data model itself.

---

## Current Prototype Review

### Verdict

The current prototype is useful as a first code sketch, but it does **not** yet meet the intended target state.

The main issue is that it behaves like a basic Tkinter data editor plus an external Sankey export, not like a dynamic household finance dashboard. The visualisation is opened as a temporary HTML file, the review workflow is incomplete, and several state-management details will become problematic once the app is used on real bank exports.

### What is worth keeping

The following parts are reasonable starting points:

- the idea of keeping a transaction-based core model;
- a deterministic transaction ID mechanism;
- immutable `Transaction`, `Rule`, and `CategoryStyle` dataclasses;
- a simple CSV importer for a normalised first format;
- a basic JSON state export/import mechanism;
- the broad separation into `core`, `io`, and `ui` modules.

These parts can be reused, but several details need to be changed.

### Main gaps

#### 1. The UI framework does not match the intended direction

The requested direction was a dynamic local GUI/web-GUI, preferably NiceGUI. The current implementation uses Tkinter. Tkinter is acceptable for tiny desktop utilities, but it is not a good fit for the desired interaction pattern:

- no embedded dynamic Plotly dashboard;
- no modern table editing workflow;
- no smooth review queue;
- no good layout for a two-page finance dashboard;
- no natural future path towards a browser-like or Android-friendly interface.

Target: replace the UI layer with a local web-style interface. NiceGUI remains the preferred direction unless a concrete packaging blocker appears.

#### 2. The Sankey is not actually dynamic

The visualisation page only has a button called `Open Sankey`. This writes a temporary HTML file and opens it in the browser. That is not the intended dynamic interaction.

Problems:

- filters update the summary table, but not an embedded Sankey;
- category colour changes only affect the next exported/opened diagram;
- the Sankey is outside the app UI;
- the temporary HTML uses `include_plotlyjs="cdn"`, which violates the local-only/offline intent;
- custom category colours can currently crash Plotly because the colour list contains `None` entries.

Target: the Sankey must be embedded in the visualisation page and update when filters, classifications, rules, or colours change.

#### 3. The review workflow is incomplete

The review table only shows unclassified transactions and allows opening a simple edit dialog. The requested workflow is broader:

- show unresolved entries clearly;
- support manual assignment;
- support rule creation with editable pattern suggestion;
- support ignoring a transaction;
- apply newly created rules to existing unclassified transactions;
- make the difference between manual overrides and rule-based classifications explicit.

The current implementation has no visible `ignore` action. It also creates a rule silently from the first word of the description, without letting the user edit the pattern. This is too brittle for real merchant strings.

Target: implement a proper review queue with explicit actions: `Assign only this`, `Create rule`, `Apply rule to matches`, and `Ignore`.

#### 4. Rule semantics are not robust enough

The current `RuleEngine` fills missing category/owner fields but never overwrites existing assignments. This creates hidden state problems:

- deleting a rule does not undo classifications that came from that rule;
- changing or adding a higher-priority rule does not reclassify old transactions;
- there is no distinction between manual classifications and rule-derived classifications;
- duplicate rule IDs are possible for rules with identical fields, which can break UI tree IDs;
- rule order is not explicitly stored, only implied by tuple order.

Target: store whether a classification was manual or rule-based. Reclassification should preserve manual overrides, but rule-based classifications should be recomputed from the current rule set.

#### 5. State model needs a small redesign

The current `AppState` is marked as frozen, but contains a mutable `dict` for `category_styles`. This is not truly immutable.

The state also lacks:

- metadata;
- schema version;
- created/updated timestamps;
- explicit person/owner configuration;
- classification provenance;
- robust import results;
- a clear distinction between raw transaction data and user classification decisions.

Target: keep the model simple, but make the state explicitly serialisable, versioned, and safe to reclassify.

#### 6. Import/export behaviour needs sharper semantics

The current CSV import appends transactions and skips duplicate IDs, which is directionally correct. However, real bank exports may contain legitimate repeated transactions with identical date, account, description, amount, and currency. The current deduplication could collapse such entries.

The current state export may also store full local source paths, which is unnecessary and can leak private file-system information.

Target: import should report how many rows were read, added, skipped, and failed. Store only the source file name by default. Add support for an optional external transaction ID later.

#### 7. Project hygiene is incomplete

The current project lacks the planned tests and has packaging inconsistencies:

- no tests are included;
- README mentions Matplotlib embedding, but the code does not embed Matplotlib;
- README mentions a `requirements.txt` path for `uv`, but no such file is provided;
- `pyproject.toml` uses Poetry, while the target prefers `uv`;
- the UI is concentrated in one large file;
- `pyinstaller` notes are not yet validated.

Target: move to a small but clean project structure with tests around core behaviour before improving the UI.

---

## Target Product State

### Product definition

The application should feel like a small local household-finance dashboard:

1. import CSV exports from bank/card accounts;
2. add new rows to the existing state;
3. classify transactions using rules;
4. review unresolved transactions;
5. create reusable rules from review decisions;
6. persist the full state to a JSON file;
7. load a previous state;
8. clear the app state when needed;
9. view a dynamic Sankey dashboard;
10. assign and persist category colours.

The app must remain local-only. No bank API, cloud sync, login, analytics, or remote backend.

---

## Target UI

### Framework

Use a local browser-style GUI. Preferred:

```text
NiceGUI + pandas + plotly
```

The app may run on `localhost`, but it must not require an external server. All state is stored locally and explicitly imported/exported by the user.

### Page 1: Data, Rules, and Review

This page manages the state.

It should contain these sections in order:

1. **State actions**
   - Import CSV
   - Import state JSON
   - Export state JSON
   - Clear state

2. **Import result panel**
   - rows read
   - added transactions
   - skipped duplicates
   - failed rows
   - currently unresolved transactions

3. **Rules editor**
   - pattern
   - category
   - owner
   - priority
   - enabled
   - edit
   - delete

4. **Review queue**
   - only unresolved and non-ignored transactions by default;
   - visible context: date, account, description, amount, currency;
   - editable category;
   - editable owner;
   - button: assign only this transaction;
   - button: create rule;
   - button: ignore transaction.

5. **Optional transaction browser**
   - all transactions;
   - filters by status, month, owner, category;
   - useful for debugging, but not required for the first pass.

### Page 2: Visualisation

This page displays the current dashboard.

It should contain:

1. **Filters**
   - month selector;
   - owner selector;
   - currency selector;
   - include income toggle;
   - include ignored toggle, disabled by default.

2. **Embedded Sankey diagram**
   - generated from the filtered current state;
   - updates after filter changes;
   - updates after rule/review changes;
   - updates after category colour changes;
   - does not write/open a temporary HTML file during normal use.

3. **Category colour editor**
   - one row per used category;
   - colour input or colour picker;
   - persisted in the exported state;
   - used in both nodes and category-related links.

4. **Summary table**
   - category;
   - owner;
   - total amount;
   - share of expenses.

---

## Target Data Model

The model should stay compact, but should explicitly distinguish raw transactions, classification decisions, and rule metadata.

### Suggested models

```python
@dataclass(frozen=True)
class Transaction:
    id: str
    date: date
    account: str
    description: str
    amount: Decimal
    currency: str
    source_file: str | None = None
    external_id: str | None = None
    category: str | None = None
    owner: str | None = None
    classification_source: Literal["manual", "rule"] | None = None
    classification_rule_id: str | None = None
    ignored: bool = False
```

```python
@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    category: str
    owner: str
    priority: int = 0
    order: int = 0
    enabled: bool = True
```

```python
@dataclass(frozen=True)
class CategoryStyle:
    category: str
    colour: str | None = None
```

```python
@dataclass(frozen=True)
class AppMetadata:
    schema_version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

```python
@dataclass(frozen=True)
class AppState:
    transactions: tuple[Transaction, ...]
    rules: tuple[Rule, ...]
    category_styles: Mapping[str, CategoryStyle]
    metadata: AppMetadata
```

### Money representation

Prefer `Decimal` for amounts. If this becomes too inconvenient for Plotly or pandas, store integer cents internally and convert to decimal values only for display.

Avoid using raw floats as the canonical money representation.

---

## Target State Semantics

### CSV import

CSV import means **append/update transaction data**.

Expected behaviour:

- existing transactions remain;
- new transactions are added;
- duplicates are skipped;
- import result is shown to the user;
- classification rules are applied after import;
- unresolved transactions appear in the review queue.

### State export

State export means **materialise the full current app state**.

The exported JSON must contain:

- transactions;
- rules;
- category styles;
- metadata.

The file must be reloadable.

### State import

State import means **replace the current in-memory state**.

The UI should make this explicit before loading:

```text
This replaces the current state. Continue?
```

### Clear

Clear means **reset the app to empty state**.

It must remove:

- transactions;
- rules;
- category styles.

It should require confirmation.

---

## Target Rule Semantics

Rules classify transactions by case-insensitive substring matching against the transaction description.

Rules are evaluated by:

1. higher priority first;
2. lower order value first;
3. stable insertion order as fallback.

Reclassification logic:

- manual classifications are preserved;
- ignored transactions remain ignored;
- rule-based classifications are recomputed when rules change;
- unclassified transactions are classified if a matching enabled rule exists;
- disabled rules are ignored.

Creating a rule from a transaction should be explicit:

```text
Description: MIGROS WIPKINGEN
Suggested pattern: migros
Category: Groceries
Owner: shared
[Save rule]
[Save rule and apply to all matches]
```

The suggested pattern must be editable.

---

## Target Sankey Semantics

Use this first structure:

```text
Income -> owner
owner -> category
```

Income transactions are positive amounts.

Expense transactions are negative amounts.

Ignored transactions are excluded by default.

Unclassified transactions may be shown under:

```text
Unassigned -> Uncategorised
```

but the default dashboard should make unresolved transactions visible as a warning, because a Sankey with many uncategorised flows is not useful.

### Colour handling

The Sankey builder must never pass `None` inside Plotly colour lists. Use either:

- no colour list at all; or
- a full colour list with valid default colours for every node/link.

Target behaviour:

- category nodes use the configured category colour;
- links ending in a category inherit that category colour;
- owner and income nodes use neutral defaults;
- unassigned/uncategorised flows use a visible warning colour.

---

## Target Project Structure

Use a compact structure:

```text
budget_app/
  pyproject.toml
  README.md
  AGENDA_TARGET_STATE.md

  src/
    budget_app/
      __init__.py
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

  examples/
    sample_transactions.csv
    sample_state.json

  tests/
    test_importers.py
    test_rules.py
    test_state.py
    test_sankey.py
```

Avoid splitting into too many files. The UI should be split by page, not by every widget.

---

## Implementation Agenda

### Pass 1: Stabilise the core model

- Add metadata and schema version.
- Replace mutable `dict` in frozen `AppState` with an immutable or safely copied mapping.
- Add classification provenance fields.
- Use `Decimal` or integer cents for amounts.
- Add explicit `enabled` and `order` fields to rules.
- Ensure rule IDs are unique even when two rules share the same pattern/category/owner.

### Pass 2: Fix classification semantics

- Implement reclassification that preserves manual overrides.
- Recompute rule-based classifications when rules change.
- Do not silently keep stale classifications after deleting or changing rules.
- Add tests for manual assignment, rule assignment, rule deletion, and priority ordering.

### Pass 3: Improve import/export

- Add an `ImportResult` object.
- Show added/skipped/failed counts after import.
- Store source file basename rather than full path.
- Keep the normalised CSV format for now.
- Add tests for duplicate detection and CSV import.

### Pass 4: Replace the UI with the target local web-style interface

- Build two pages: Data/Rules/Review and Visualisation.
- Use embedded tables for rules and review queue.
- Add explicit buttons for assign, create rule, and ignore.
- Keep all state transitions routed through `AppState` methods.

### Pass 5: Implement embedded dynamic visualisation

- Embed the Plotly Sankey in the visualisation page.
- Update it when filters change.
- Update it after imports, rule changes, review assignments, and colour edits.
- Remove normal use of temporary HTML files.
- Avoid CDN dependencies.

### Pass 6: Add category colour handling

- Add editable colours for all used categories.
- Store colours in state export.
- Apply colours safely in Sankey builder.
- Add tests that Sankey generation works with partially assigned colours.

### Pass 7: Add tests and packaging notes

- Add tests for core logic.
- Validate one-command startup.
- Switch to `uv` if desired.
- Add packaging instructions for PyInstaller.
- Keep packaging notes honest if not fully tested.

---

## Minimum Acceptance Criteria for the Next Version

The next version is acceptable when all of the following are true:

- The app starts with one documented command.
- The app has two clear pages: Data/Rules/Review and Visualisation.
- CSV import appends to the current state and reports added/skipped counts.
- Duplicate import does not duplicate transactions.
- State export writes the full state to JSON.
- State import restores the previous state.
- Clear resets the app after confirmation.
- Rules can be added, edited, disabled, and deleted.
- Unclassified transactions appear in a review queue.
- A transaction can be manually assigned to category and owner.
- A transaction can be ignored.
- A rule can be created from a transaction with an editable pattern.
- New rules can be applied to matching unclassified transactions.
- Manual overrides are not destroyed by reclassification.
- Rule-based classifications are recomputed when rules change.
- The Sankey is embedded in the visualisation page.
- The Sankey updates after filter changes.
- Category colours can be edited and persisted.
- Sankey generation works even if only some categories have colours.
- Ignored transactions are excluded from the Sankey by default.
- Core behaviours are covered by tests.

---

## Non-Goals

Do not implement these in the next pass:

- bank API integration;
- Android app;
- cloud sync;
- user accounts;
- forecasting;
- recurring transaction detection;
- multi-currency conversion;
- advanced budgeting envelopes;
- automatic merchant normalisation beyond simple rules.

These can be revisited later, after the local CSV workflow is stable.

---

## Recommended Immediate Next Step

Do not polish the current Tkinter UI.

Instead:

1. keep the useful core pieces;
2. fix the state and rule semantics;
3. add tests;
4. replace the UI with the target dynamic local interface;
5. make the Sankey embedded and reactive.

The current prototype should be treated as a scaffold, not as the foundation of the final interaction model.
