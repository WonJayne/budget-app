# Budget app review and next steps

Reviewed 29 October 2026 against commit `05a297a`, with a clean working tree before review. Scope: all application modules, test modules, example data, dependency configuration, README, and the existing agenda.

The app has a useful foundation: immutable state, a testable core, rule provenance, local operation, and an embedded dashboard. The next development pass should focus on trustworthy imports, bounded UI work, and explicit transfer reconciliation. A database or a full rewrite is unnecessary for these changes.

The performance concern is justified, with a distinction: there are multiplicative costs and quadratic workflows, but most individual aggregation functions are linear. More urgent correctness gaps can change reported balances or silently lose user work. Fix those alongside the first performance improvements.

## First fixes completed

Implemented on 29 October 2026. The findings below describe the original reviewed revision; this checklist records the changes since that review.

- [x] Deduplicate incoming IDs in append, direct-add, and replacement batches; correct replacement missing-row counts. Duplicate-ID validation for backup import remains open under F01.
- [x] Generate independent IDs for newly created manual entries, rules, and budget targets. Existing saved IDs and imported transaction identity are preserved. Broader state-boundary uniqueness validation remains open under F02.
- [x] Reject invalid CSV dates, missing required values, and non-finite amounts with row-number messages; retain the original upload filename. Additional import-format policies and parsing optimization remain open under F04.
- [x] Classify only newly appended rows. Transaction-edit optimization and rule indexing remain open under F07.
- [x] Bucket the yearly overview by month after one ledger filtering pass. Shared dashboard aggregates and budget-target optimization remain open under F08.
- [x] Apply savings-target owner filters. Category semantics and overlapping target plans remain open under F11.
- [x] Separate ungrouped transfers using full IDs and typed internal group keys; preserve transfer group and note when assigning a transaction. F13 is addressed.
- [x] Preserve the All period selection and default manual-entry dates within the selected year or month. Filter recovery after importing a different state remains open under F15.
- [x] Apply the owner filter to the yearly overview and respect the transfer visibility switch. Other dashboard filter semantics remain open under F16.
- [x] Reject blank rule patterns in the UI and prevent legacy blank patterns from matching every transaction. Rule previews and override controls remain open under F17.
- [x] Handle single-pass transaction iterables correctly in cash-flow totals, yearly overview, and budget comparison. F20 is addressed.

The statement-replacement workflow still discards overrides, mixed-currency totals still require isolation, and transfer matching still uses aggregate groups. Those larger changes remain priorities rather than being implicitly resolved by this pass.

Validation of this pass: **128 tests passed in 3.02 seconds**, including 29 added regression cases. Local startup returned HTTP 200. Headless UI checks verified that All survives refresh and the assignment dialog preserves transfer metadata. No browser visual assessment was performed.

## Original verification

- Existing suite: **99 passed in 2.15 seconds**, using `uv run --offline --no-sync pytest -q -p no:cacheprovider` against the existing environment.
- Startup: launched the application, received HTTP 200 from `http://127.0.0.1:8080`, checked that the returned page contained the app title, and stopped the launched process.
- Additional executable probes reproduced the defects identified as reproduced below. These are findings, not fixes or new passing regression tests.
- No browser interaction, visual layout assessment, real household statements, or end-to-end browser latency measurements were performed. UI bottlenecks below are conclusions from the render and callback paths.
- Initial restricted test runs hit Windows temporary-directory permissions; the successful run used the necessary local permissions. Startup similarly required permission for NiceGUI's process communication.

## Priority and execution order

P1 means incorrect financial results, lost work, or a major usability blocker. P2 means a substantial correctness, performance, or usability improvement. P3 means maintenance and later product work. Items are intentionally small enough to become separate changes.

| Order | Work package | Findings | Completion check |
| --- | --- | --- | --- |
| 1 | Protect identity and import integrity | F01 to F04 | Batch deduplication, unique created IDs, safe replacement preview, invalid rows rejected |
| 2 | Make reported money consistent | F05, F10, F11 | Currency isolation, sign validation, distinct Sankey node identities, correct budget scopes |
| 3 | Bound review and refresh work | F06 to F08 | Paged review, selective refresh, incremental imports and transaction edits |
| 4 | Make transfers explicit and reviewable | F09, F12, F13 | Confirmed links, global reconciliation before display filtering, exceptions queue |
| 5 | Protect daily work and clarify views | F14 to F17 | Deliberate save lifecycle, working All period, consistent filters, rule preview |
| 6 | Harden and measure | F18 to F21 | Exact money policy, migration tests, iterable correctness, reproducible performance baselines |

## Performance findings

Let N be transactions, R rules, B active budget targets, U unresolved entries, and K imported batches or individual edits. Description length also affects substring matching.

### F06 Bound rendering and refresh work

**P1.** `ui/main.py:73` refreshes both pages after every state change. `ui/pages_data.py:722` rebuilds a card and several controls for every unresolved transaction, across the entire history, even when the ledger shows one month. Ledger rows are also fully materialized and supplied to `ui.table` at `ui/pages_data.py:584`; browser pagination alone would not bound server work or payload size. The inner Rules and Review tabs at `ui/pages_data.py:690` have no associated tab panels, so they do not isolate that content.

One action can therefore rebuild O(U) UI elements plus the ledger, dashboard, yearly overview, budget section, and colour editor. Resolving U entries one at a time creates O(U²) cumulative review rendering. This is a stronger explanation for interactive slowness than optimizing small dictionary aggregations.

- [ ] Render only a bounded review page, initially 50 entries, with period/source/status filters and a total count.
- [ ] Page ledger results before serializing rows. Add search and bulk assign/ignore actions implemented as one state transition.
- [ ] Give Rules and Review actual panels or separate render regions. Build expensive hidden views on demand.
- [ ] Refresh the region affected by an action; mark hidden views dirty and refresh them when opened.
- [ ] Verify that ignoring one review row does not rebuild the chart, yearly report, or every other review row. Keep open dialogs and selected tabs stable across updates.

### F07 Avoid classifying the whole ledger on routine changes

**P2.** `core/rules.py:43` scans the ordered rules for each transaction: worst-case O(NR), plus rule ordering O(R log R). This becomes quadratic only if R grows with N. `core/state.py:151` classifies all old and new rows on every append, while `update_transaction` and `update_manual_transaction` reapply rules to the whole ledger after editing one row.

Adding N entries individually can therefore accumulate O(N²R) classification work when old rows remain eligible, plus tuple copying. An ignore operation itself is O(N), not O(N²); applying it separately to every entry is O(N²), even before UI work.

- [ ] Classify only new transactions on append and only the edited row on a transaction edit. Keep complete reclassification for rule/profile changes.
- [ ] Add batch update operations that scan the ledger once and publish one state change.
- [ ] Reuse an ordered rule engine until rules change. Precompute normalized patterns and normalize each description once.
- [ ] Partition eligible rules by source and sign while preserving priority, source specificity, and insertion order. Do not concatenate buckets in a way that changes winners.
- [ ] Add a transaction ID lookup derived once per state revision for callbacks. Immutable tuple replacement remains O(N); that is acceptable until measured otherwise.
- [ ] Keep the simple substring matcher until profiling justifies a more complex matching algorithm.

### F08 Aggregate once for each revision and filter

**P2.** `core/summaries.py:387` runs `_target_actual` across transactions for every target: O(NB). `yearly_overview` at line 275 performs two full input scans for each of 12 months, about 24N filtering visits. That is still O(N), not O(N²). The dashboard separately filters and aggregates overlapping data for cards, transfers, Sankey, budgets, and summaries on each refresh.

- [ ] Build monthly aggregates in one pass, grouped by currency, flow type, category, and owner. Support exact and wildcard target scopes without rescanning transactions for every target.
- [ ] Reuse the filtered transaction tuple for cards, summary, and chart where their filter semantics agree.
- [ ] Cache derived results by state revision and filter values. Invalidate classification results on rule changes, and chart styles on colour changes, without retaining all historical states indefinitely.
- [ ] Keep transfer reconciliation separate from period aggregates as described below.

### Measured scaling

Synthetic local measurements, median of three runs, milliseconds. Every row was an unassigned May outflow; every rule deliberately failed to match. Budget measurements included construction of N/100 category targets; repeated-ignore measurements called the current core operation once for every row, without UI refreshes.

| Transactions | Rules | Full classification | Budget comparison | Ignore every row individually |
| --- | --- | --- | --- | --- |
| 1,000 | 100 | 36.30 | 6.39 | 74.98 |
| 2,000 | 200 | 150.97 | 31.90 | 272.38 |
| 4,000 | 400 | 601.15 | 106.76 | 1,072.57 |

Doubling both N and R produces approximately four times the classification work. Repeated individual ignores also approach fourfold growth. These are core timings, not estimates of browser response time; early rule matches and manual assignments reduce classification work.

Reproduction recipe: construct N distinct `Transaction` objects with amount -100, date 2026-05-31, description `payment`, currency CHF; construct R outflow rules whose patterns are `no-match-0`, `no-match-1`, etc.; time `RuleEngine(rules).classify_many(rows)`. For budgets, create N/100 outflow targets for category Rent and call `budget_comparison`. For ignores, start with `AppState(transactions=rows)` and call `state = state.ignore_transaction(tx.id)` for each row. Construct inputs outside the timed region where practical and use the same data for each repetition.

## Data integrity findings

### F01 Deduplicate within each incoming batch

**P1, reproduced.** `core/state.py:105` and `:151` compare incoming IDs only with IDs already in state. Importing `(tx, tx)` into an empty state adds both rows and reports two added, zero skipped. The duplicate ID also makes edit/delete callbacks act on multiple entries and breaks table identity.

- [ ] Maintain a running seen set across both existing and incoming IDs, and count skipped rows accurately.
- [ ] Enforce unique IDs when loading a full backup and when replacing source periods; resolve conflicts explicitly rather than keeping ambiguous rows.
- [ ] Add tests for duplicates within one file, across files, and in a replacement upload.

### F02 Stop using collection length to create unique IDs

**P1, reproduced for manual entries.** `core/state.py:175` salts IDs with the current transaction count. Create three manual entries, delete the first, then recreate the third entry's fields: the remaining third entry's ID is reused and the new entry is silently skipped. Rule and target dialogs use the same collection-length pattern for their generated IDs (`ui/pages_data.py:257`, `ui/pages_visualisation.py:67`), exposing equivalent reuse after deletion when the other inputs match.

- [ ] Use independent unique IDs for manually created transactions, rules, targets, and future transfer links. Keep imported identity separate.
- [ ] Validate uniqueness at state boundaries. Updates and deletes should target exactly one entity.
- [ ] Test create/delete/recreate sequences and roundtrip IDs through JSON.

### F03 Make statement replacement safe and explicit

**P1, reproduced.** `core/state.py:112` deletes all CSV entries for the selected source between the upload's minimum and maximum dates, then inserts the raw upload. Even unchanged rows lose manual categories, ignored flags, edits, and transfer metadata. A partial upload can delete unrelated accounts sharing the source and intervening rows omitted from the upload. The `missing` report is simply the deleted-row count, not a set difference.

- [ ] Ask for the intended statement range explicitly; row min/max cannot express an empty period or missing boundary dates.
- [ ] Prepare a preview showing additions, unchanged rows, removals, conflicts, and user overrides that would be affected. Confirm the concrete replacement before committing it.
- [ ] Preserve overrides and ignore flags for reliably matched rows. Separate original imported fields from edits so reconciliation can compare both.
- [ ] Scope replacement to a stable feed/account identity. Require an explicit decision for changed rows that cannot be reliably matched.
- [ ] Test sparse and empty statements, two accounts sharing a source, edited entries, and manual transfer links.

### F04 Validate imports and retain real source provenance

**P1, reproduced for blank amounts.** `core/importers.py:16` uses pandas inference without validating row values. A blank amount becomes NaN and imports as a transaction with no flow type; missing strings can become the literal `nan`. Invalid dates or amounts otherwise abort through callback exceptions without a useful row report. The upload callback passes a random temporary filename to the importer, so `source_file` stores that name rather than the user's filename (`ui/pages_data.py:174`, `core/importers.py:38`).

- [ ] Reject non-finite amounts, invalid dates, and missing required strings with row numbers and a summary. Parse into a temporary result before changing state.
- [ ] Define accepted date, decimal, whitespace, currency-case, encoding, and delimiter formats. Avoid silent locale guessing.
- [ ] Pass the original upload filename separately from the temporary storage path, or import from bytes/text directly.
- [ ] Parse dates in a vectorized pass and use `itertuples` instead of `iterrows` after validation. This reduces overhead; the current importer is linear, not quadratic.
- [ ] Define duplicate identity deliberately: prefer bank transaction references where available. The current hash cannot distinguish two legitimate identical same-day payments, and cents formatting can collapse finer amounts. A within-batch dedup fix alone does not solve this identity problem.

### F05 Keep currencies separate in every monetary result

**P1, confirmed in code.** `ui/pages_visualisation.py:25` defaults currency to All and passes `None` as the currency filter. Cards, Sankey, yearly summaries, and transfer-monitor totals then add CHF, EUR, etc. as if they were the same unit. `core/sankey.py:167` labels all hover amounts CHF, even when a different currency is selected. Transfer groups are correctly separated by currency, but `transfer_monitor_totals` subsequently sums across them.

- [ ] Default to a single currency. In an All currencies view, show independent totals and charts per currency, or disable combined monetary totals.
- [ ] Pass the actual currency into chart labels and exports. Include currency on every monetary summary.
- [ ] Add CHF/EUR fixtures proving that mixed inputs never produce an unlabeled combined balance. No exchange-rate service is needed.

## Transfer reconciliation

### F09 Separate classification from confirmed matching

**P1, reproduced.** `core/summaries.py:231` groups transfers by free-text label and currency, then calls the minimum of incoming and outgoing totals the matched amount. Two opposite entries on the same account can be reported as balanced. The same-month/date/amount strategies in `core/models.py:151` can merge several unrelated payments with equal amounts; a fixed label can hide unmatched movements across long periods. A balanced aggregate is useful monitoring information, but it does not prove that particular entries are counterparts.

Keep transfer classification because a genuine internal movement should not inflate household inflow/outflow. Add reconciliation as a distinct concept with explicit links between ledger entries. Rules should propose candidates or classify entries; they should not establish a confirmed pair merely by generating the same string.

- [ ] Introduce stable account/feed IDs with labels, currency, ownership, and whether each account is inside the household budget boundary. Keep import filenames separate from account identity.
- [ ] Add an immutable transfer-link model containing its own ID, member transaction IDs, allocated amounts, status/provenance, and notes. Start with one-to-one same-currency links; support explicit split allocations later.
- [ ] Suggest candidates using opposite signs, equal amount in currency minor units, different compatible accounts, and a configurable booking-date window. Shared bank references should strengthen a suggestion.
- [ ] Index candidates by currency and amount, then search a bounded date window. This avoids comparing every transaction with every other transaction. Dense same-amount buckets can still be large; cap suggestions and retain ambiguity.
- [ ] Let the user confirm, unlink, or choose another counterpart. Never consume one amount twice. Manual decisions survive rule edits.
- [ ] Present missing, ambiguous, confirmed, and intentionally external/untracked cases distinctly. Keep an audit trail of the decision.
- [ ] Initially migrate legacy group strings as labels or unverified groups; do not silently promote them to confirmed matches.

Suggested user workflow: classify or select a potential transfer, inspect a short list of counterpart candidates, then confirm the pair. Show date, account, owner, currency, amount, and source for each side. Provide “counterpart account is not tracked” as an explicit resolution, rather than forcing a fabricated balancing entry.

### F12 Reconcile globally before filtering a view

**P2, reproduced for month boundaries.** A linked -100 on 31 May and +100 on 1 June is balanced across the ledger, but the current monthly monitor reports each side as single-sided. `ui/pages_visualisation.py:171` filters transactions before building transfer groups, and `core/summaries.py:275` repeats grouping independently for every month. Owner filtering or hiding an ignored counterpart can similarly remove the other side from the visible set.

- [ ] Determine reconciliation status against the full eligible ledger first, then select visible members for the chosen period/owner.
- [ ] Distinguish “counterpart outside this view” from “counterpart missing from imported data.” Define the policy for an ignored or deleted counterpart explicitly.
- [ ] Report booked transfer-in/out amounts by their actual dates. Define how matched-transfer volume is counted so annual totals do not double-count a pair spanning months.
- [ ] Test month/year boundaries, different owners, ignored members, edits, and counterpart deletion.

### F13 Fix group identity and preserve metadata during assignment

**P2, reproduced for prefix collisions; assignment path confirmed in code.** `_transfer_group_label` at `core/summaries.py:201` uses only the first eight characters of ungrouped transaction IDs. Two ungrouped entries with the same prefix become one group and can appear matched. Display labels are also used as identities. Separately, `assign_dialog` at `ui/pages_data.py:307` does not pass existing transfer group/note values into `update_transaction`, whose defaults clear them.

- [ ] Use typed keys containing the full transaction or link ID; generate short labels only for display.
- [ ] Preserve transfer metadata in assignment-only changes. Remove it intentionally when converting an entry into an ordinary flow.
- [ ] Test IDs sharing a prefix, explicit labels resembling generated labels, and assigning a previously unclassified transfer that already has notes.

### Budget boundary and exceptional transfers

The README already distinguishes tracked private-to-shared movements from contributions coming from untracked accounts. Make that distinction a visible account setting and review decision. If the boundary changes, preview the effect on past cash-flow totals before applying it.

Credit-card settlements should be neutral when card purchases are already imported. If only the paying bank account is tracked, excluding the settlement can hide spending; offer a clear accounting choice. Savings and brokerage transfers represent asset allocation when both sides are inside the selected boundary. They should not require inventing ordinary expenses merely to display allocation goals.

For fees and foreign exchange, do not silently tolerate a difference until a group looks balanced. Record an explicit fee outflow or an explicit currency conversion with both amounts and the chosen rate. A tolerance is for rounding, not evidence of a counterpart. These are later extensions after trustworthy same-currency pairing.

## Calculation and dashboard findings

### F10 Validate financial invariants and distinguish Sankey node identities

**P1, reproduced.** JSON import accepts `cash_flow_type="inflow"` with amount -100; `cash_flow_totals` then returns a negative inflow. Literal type hints do not validate runtime data. `core/sankey.py:106` keys nodes solely by visible label. An outflow category named Household pool merges with the central node and creates a cycle. A category used on both sides of the chart also merges inflow and outflow category nodes.

- [ ] Validate flow/sign consistency, finite amounts, enum values, required strings, unique IDs, and references at import and core update boundaries. Handle zero amounts consistently.
- [ ] Use typed node keys such as `('pool',)`, `('category', 'inflow', category)`, and `('owner', 'outflow', owner)`. Keep labels separate.
- [ ] Test reserved labels, one category used for both flow directions, mismatched JSON signs, and malformed records.

### F11 Respect target scopes and define overlapping plans

**P2, reproduced for savings scope.** `_target_actual` at `core/summaries.py:362` returns full household balance for savings targets before checking owner or category. A Flo savings target includes Nina's movements. `budget_plan_totals` sums target amounts even when a broad household target overlaps category or owner targets, while actuals remain whole-household totals.

- [ ] Apply the supported owner scope to savings actuals, or remove unsupported selectors for savings targets. Explain what category means for a savings target before allowing it.
- [ ] Decide whether targets form an additive plan or independent monitoring limits. Prevent overlaps in additive totals, or exclude non-additive limits from plan totals.
- [ ] Make budget period/currency independence from the chart explicit, or synchronize them. Ensure the chosen budget currency remains selectable after a state import.
- [ ] Add tests for scoped savings, overlapping targets, negative targets, and inactive targets. Retain the existing caveat about simple linear projections; scheduled fixed payments need a separate projection model if introduced.

### F15 Preserve the All period and selected manual-entry year

**P2, confirmed in code.** `ui/pages_data.py:528` resets any period whose year is not in available years. All has `year=None`, so selecting All immediately resets to the latest month. In `manual_entry_dialog` at line 374, a selected Year without a month falls back to today's date, which can create an entry outside the year being viewed.

- [ ] Validate year membership only in Year/Month mode. Test All on both empty and populated states.
- [ ] Default manual entry dates within the selected year/month and explain the chosen date.
- [ ] Keep filter values and visible selectors synchronized after loading a different backup or deleting the last entry for a selected owner/source.

### F16 Make dashboard filter semantics consistent

**P2, confirmed in code.** The yearly overview call ignores the selected owner. Category summary deliberately switches to the selected whole year and includes inflows, even when the top selector shows Month or inflows are disabled. Disabling inflows also changes the balance cards and introduces a synthetic deficit equal to selected outflows. The transfer monitor condition `show_transfers or transfer_count` displays transfers even with its switch off.

- [ ] Decide which filters apply to each panel and state exceptions beside that panel. Prefer shared filters for cards, chart, and corresponding summary.
- [ ] Keep full-period balance visible when choosing an outflow-only chart, or label the cards explicitly as filtered totals.
- [ ] Make the transfer visibility switch control visibility; keep a separate warning/count for unresolved transfers if desired.
- [ ] Test owner-filtered yearly reports and filter combinations with a small known ledger.

## Persistence and maintainability

### F14 Add a deliberate local save lifecycle

**P1 product gap, confirmed in code.** `ui/main.py:70` starts each created UI with empty in-memory state. The UI has manual download/import backups but does not load or save a working file. Browser reload or a new session can therefore lose unexported work. Successful JSON export alone is not durable daily-use persistence.

- [ ] Define whether there is one shared local workspace or independent browser sessions. Avoid concurrent sessions silently overwriting each other.
- [ ] Add an explicit Open/Save working-file flow, saved/unsaved status, and recovery. Local autosave is a reasonable option after the workspace model is clear.
- [ ] Write through a temporary sibling file and atomically replace the working JSON; retain a recoverable previous version. Keep manual backup export.
- [ ] Test reload/restart recovery, failed saves, invalid imports leaving the old state intact, and concurrent changes. Keep all data local and do not introduce a database.

### F17 Preview rule effects and keep overrides deliberate

**P2.** Rule forms accept an empty pattern, which matches every compatible description. There is no affected-row preview or conflict explanation. Editing an already classified entry sets its assignment source to manual, even when the user only changes a non-classification field; this can unexpectedly freeze rule-derived category/owner assignments. There is no clear “return to rules” action.

- [ ] Reject blank rule patterns unless the user deliberately chooses an explicit catch-all rule.
- [ ] Preview affected rows, match counts, and winning rule before saving; explain source specificity and priority.
- [ ] Store field edits separately from classification overrides where needed. Provide an explicit reset-to-rules action.
- [ ] Preserve current manual-override behavior with regression tests while introducing deliberate override controls.

### F18 Use an explicit money representation and rounding policy

**P2.** Amounts, target values, aggregates, hashes, and transfer tolerances currently use floats and assume two decimal places. Small binary remainders can produce phantom savings/deficit nodes because the Sankey compares balance directly with zero.

- [ ] Choose integer minor units or Decimal, define currency precision and rounding at import/export boundaries, and use the same policy for matching and totals.
- [ ] Add a schema migration rather than changing interpretation of old saved amounts silently.
- [ ] Test cent arithmetic, exact zero, repeated summation, invalid non-finite numbers, and currencies with supported nonstandard precision.

### F19 Make schema handling and import errors explicit

**P2.** `io/state_json.py:84` reads and preserves a schema number but does not dispatch migrations or reject unsupported future versions. Several missing legacy fields have good defaults, but invalid shapes, types, and enum-like values are only partially checked. Full backup/profile callbacks replace state directly after parsing, without a friendly validation report or replacement preview. `save` writes directly to its destination.

- [ ] Add a current schema version, ordered migrations, and clear handling for future versions. Validate a complete candidate state before swapping it in.
- [ ] Distinguish full backup and profile formats so uploading the wrong kind cannot silently replace useful state with empty content.
- [ ] Present actionable import errors and a replacement summary. Apply profile changes and rule reclassification as one transaction.
- [ ] Cover old fixtures, corrupt records, duplicate IDs, missing link members, and future-version rejection. Update examples and README with every schema change.

### F20 Honor iterable contracts in aggregation helpers

**P2, reproduced.** `cash_flow_totals` at `core/summaries.py:158` iterates its argument twice. Given a generator containing +100 and -50 it returns inflow 100, outflow 0, balance 100. `yearly_overview` and `budget_comparison` also repeatedly consume arguments advertised as Iterable. Current UI callers mostly pass tuples, which hides the defect.

- [ ] Aggregate in one pass, materialize once at an API boundary, or narrow the declared contract to reusable sequences where appropriate.
- [ ] Add generator-input tests for public helpers and avoid repeatedly materializing inside target/month loops.

### F21 Maintain a compact test and documentation baseline

**P3.** Existing tests cover many intended semantics well, particularly rule provenance and transfer exclusion, but do not cover the defects above. `AGENDA_TARGET_STATE.md` still describes a Tkinter prototype and external chart export, even though NiceGUI and an embedded chart are implemented. `AGENTS.md` says ties use insertion order while the implemented and README-described rule order also prefers source-specific rules. The project requires Python 3.10+, while the tested environment here uses Python 3.12.

- [ ] Mark the old agenda's prototype critique as historical and use this list for the next implementation pass; preserve still-useful product goals.
- [ ] Align AGENTS and README with the chosen source-specific rule ordering and transfer model. Correct claims such as grouping strategy `none` leaving rule-derived fields untouched when reapplication actually recalculates them.
- [ ] Add regression tests with each fix, plus a compact end-to-end core scenario covering import, overrides, transfers, period reporting, and backup roundtrip.
- [ ] Add a local benchmark script using 1k/10k/100k rows, realistic rule counts, matched/unmatched rules, unresolved review rows, and multiple currencies. Track core compute time separately from UI construction, payload size, and browser interaction latency.
- [ ] Set performance budgets after collecting an interactive baseline on the user's machine. Verify near-linear scaling at fixed R/B and document deliberate multiplicative cases.
- [ ] Verify supported Python/dependency combinations and add a minimal automated test workflow if wanted. Pin reproducible releases through the existing lockfile; no dependency upgrade is needed for this review.

## First implementation pass

Start with F01 and F02 plus regression tests; these are small changes that remove ambiguous state. Next, implement validation and a replacement preview from F03/F04, and currency isolation from F05. Then bound review rendering and narrow refreshes before pursuing deeper matcher optimization. Design the transfer link schema and its migration after identity and import semantics are stable.

Keep current strengths throughout: local-only execution, immutable core objects, manual assignment preservation, stable imported IDs when editing, a Sankey derived from ledger state, and explicit All/Year/Month periods. Each work package should preserve JSON roundtrip behavior, update relevant examples and documentation, and pass the full test suite before the next package starts.
