"""Tkinter user interface for the budget GUI application.

This module defines a simple two‑page GUI using Tkinter.  The first
page allows users to import transactions, manage rules, review
unclassified entries and persist state.  The second page provides
filter controls, category colour editing and a button to generate an
interactive Sankey diagram in the default web browser.

The UI is intentionally minimal and emphasises clarity over visual
flair.  Most actions open modal dialogs for user input and provide
immediate feedback by refreshing the display.  The application state
is immutable; modifications produce a new state object which is then
classified via the rule engine.
"""

from __future__ import annotations

import os
import tempfile
import webbrowser
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from tkinter import ttk

import pandas as pd

from ..core.importers import TransactionImporter
from ..core.models import CategoryStyle, Rule, Transaction, _generate_id
from ..core.rules import RuleEngine
from ..core.sankey import SankeyBuilder
from ..core.state import AppState
from ..io.state_json import load_state, save_state


class BudgetApp:
    """Main application class encapsulating UI and state."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Budget GUI Application")
        self.state: AppState = AppState.empty()
        self.rule_engine = RuleEngine(self.state.rules)
        self.sankey_builder = SankeyBuilder()
        self.selected_month: Optional[str] = None
        self.selected_owner: Optional[str] = None
        self.include_income: tk.BooleanVar = tk.BooleanVar(value=True)
        self.include_ignored: tk.BooleanVar = tk.BooleanVar(value=False)
        self._build_ui()
        self._refresh_all()

    # ------------------------------------------------------------------
    # UI construction
    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        # Data page
        self.data_frame = ttk.Frame(notebook)
        notebook.add(self.data_frame, text="Data & Rules")
        self._build_data_page(self.data_frame)
        # Visualisation page
        self.viz_frame = ttk.Frame(notebook)
        notebook.add(self.viz_frame, text="Visualisation")
        self._build_viz_page(self.viz_frame)

    def _build_data_page(self, frame: ttk.Frame) -> None:
        # Top button bar
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(button_frame, text="Import CSV", command=self._import_csv).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Export state", command=self._export_state).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Import state", command=self._import_state).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Clear all data", command=self._clear_state).pack(side="left", padx=2)

        # Rules section
        rules_frame = ttk.LabelFrame(frame, text="Classification Rules")
        rules_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        # Rule tree
        columns = ("pattern", "category", "owner", "priority")
        self.rule_tree = ttk.Treeview(rules_frame, columns=columns, show="headings", selectmode="browse", height=6)
        for col in columns:
            self.rule_tree.heading(col, text=col.title())
            self.rule_tree.column(col, width=120, anchor="w")
        self.rule_tree.pack(fill="both", expand=True, side="left", padx=(0, 5), pady=5)
        # Rule buttons
        rule_btn_frame = ttk.Frame(rules_frame)
        rule_btn_frame.pack(fill="y", side="left", pady=5)
        ttk.Button(rule_btn_frame, text="Add rule", command=self._add_rule_dialog).pack(fill="x", pady=(0, 5))
        ttk.Button(rule_btn_frame, text="Delete selected", command=self._delete_selected_rule).pack(fill="x")

        # Review section
        review_frame = ttk.LabelFrame(frame, text="Unclassified Transactions")
        review_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        review_columns = ("date", "account", "description", "amount", "currency", "category", "owner")
        self.review_tree = ttk.Treeview(review_frame, columns=review_columns, show="headings", selectmode="browse", height=8)
        for col in review_columns:
            self.review_tree.heading(col, text=col.title())
            # Adjust column widths
            width = 90 if col != "description" else 200
            self.review_tree.column(col, width=width, anchor="w")
        self.review_tree.pack(fill="both", expand=True, side="left", padx=(0, 5), pady=5)
        self.review_tree.bind("<Double-1>", self._on_edit_unclassified)
        # Review buttons
        rev_btn_frame = ttk.Frame(review_frame)
        rev_btn_frame.pack(fill="y", side="left", pady=5)
        ttk.Button(rev_btn_frame, text="Edit selected", command=self._edit_selected_unclassified).pack(fill="x", pady=(0, 5))

    def _build_viz_page(self, frame: ttk.Frame) -> None:
        # Filters and controls
        filters_frame = ttk.Frame(frame)
        filters_frame.pack(fill="x", padx=5, pady=5)
        # Month selector
        ttk.Label(filters_frame, text="Month:").pack(side="left")
        self.month_var = tk.StringVar(value="All")
        self.month_combo = ttk.Combobox(filters_frame, textvariable=self.month_var, state="readonly", width=10)
        self.month_combo.pack(side="left", padx=(0, 5))
        self.month_combo.bind("<<ComboboxSelected>>", lambda e: self._on_filter_change())
        # Owner selector
        ttk.Label(filters_frame, text="Owner:").pack(side="left")
        self.owner_var = tk.StringVar(value="All")
        self.owner_combo = ttk.Combobox(filters_frame, textvariable=self.owner_var, state="readonly", width=10)
        self.owner_combo.pack(side="left", padx=(0, 5))
        self.owner_combo.bind("<<ComboboxSelected>>", lambda e: self._on_filter_change())
        # Include income toggle
        ttk.Checkbutton(filters_frame, text="Include income", variable=self.include_income, command=self._on_filter_change).pack(side="left", padx=(0, 5))
        # Include ignored toggle
        ttk.Checkbutton(filters_frame, text="Include ignored", variable=self.include_ignored, command=self._on_filter_change).pack(side="left", padx=(0, 5))
        # Sankey button
        ttk.Button(filters_frame, text="Open Sankey", command=self._open_sankey).pack(side="right")

        # Category colours editor
        styles_frame = ttk.LabelFrame(frame, text="Category Colours")
        styles_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.style_tree = ttk.Treeview(styles_frame, columns=("category", "colour"), show="headings", height=6)
        self.style_tree.heading("category", text="Category")
        self.style_tree.heading("colour", text="Colour")
        self.style_tree.column("category", width=200, anchor="w")
        self.style_tree.column("colour", width=100, anchor="w")
        self.style_tree.pack(fill="both", expand=True, side="left", padx=(0, 5), pady=5)
        # Style buttons
        style_btn_frame = ttk.Frame(styles_frame)
        style_btn_frame.pack(fill="y", side="left", pady=5)
        ttk.Button(style_btn_frame, text="Change colour", command=self._change_category_colour).pack(fill="x", pady=(0, 5))

        # Summary table
        summary_frame = ttk.LabelFrame(frame, text="Summary")
        summary_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.summary_tree = ttk.Treeview(summary_frame, columns=("category", "owner", "total", "share"), show="headings", height=6)
        for col in ("category", "owner", "total", "share"):
            self.summary_tree.heading(col, text=col.title())
            width = 120 if col != "category" else 200
            self.summary_tree.column(col, width=width, anchor="w")
        self.summary_tree.pack(fill="both", expand=True, pady=5)

    # ------------------------------------------------------------------
    # State management and classification
    def _classify(self) -> None:
        """Reclassify all transactions using the current rules."""
        self.rule_engine = RuleEngine(self.state.rules)
        classified = self.rule_engine.classify_many(self.state.transactions)
        # Preserve ignored flags and explicit assignments where rules would override
        # But classification method already respects existing category/owner
        self.state = replace(self.state, transactions=classified)

    # ------------------------------------------------------------------
    # UI refresh helpers
    def _refresh_all(self) -> None:
        self._classify()
        self._refresh_rules()
        self._refresh_unclassified()
        self._refresh_filters()
        self._refresh_styles()
        self._refresh_summary()

    def _refresh_rules(self) -> None:
        # Clear and repopulate the rule tree
        for i in self.rule_tree.get_children():
            self.rule_tree.delete(i)
        for rule in self.state.rules:
            self.rule_tree.insert("", "end", iid=rule.id, values=(rule.pattern, rule.category, rule.owner, rule.priority))

    def _get_unclassified(self) -> List[Transaction]:
        return [tx for tx in self.state.transactions if (tx.category is None or tx.owner is None) and not tx.ignored]

    def _refresh_unclassified(self) -> None:
        for i in self.review_tree.get_children():
            self.review_tree.delete(i)
        for tx in self._get_unclassified():
            self.review_tree.insert(
                "",
                "end",
                iid=tx.id,
                values=(
                    tx.date.isoformat(),
                    tx.account,
                    tx.description,
                    f"{tx.amount:.2f}",
                    tx.currency,
                    tx.category or "",
                    tx.owner or "",
                ),
            )

    def _refresh_filters(self) -> None:
        # Populate month and owner comboboxes
        months = sorted({tx.date.strftime("%Y-%m") for tx in self.state.transactions})
        owners = sorted({tx.owner for tx in self.state.transactions if tx.owner})
        # Insert 'All' as first option
        month_options = ["All"] + months
        owner_options = ["All"] + owners
        current_month = self.month_var.get() if hasattr(self, "month_var") else "All"
        current_owner = self.owner_var.get() if hasattr(self, "owner_var") else "All"
        self.month_combo['values'] = month_options
        if current_month in month_options:
            self.month_var.set(current_month)
        else:
            self.month_var.set("All")
        self.owner_combo['values'] = owner_options
        if current_owner in owner_options:
            self.owner_var.set(current_owner)
        else:
            self.owner_var.set("All")

    def _refresh_styles(self) -> None:
        # Populate the category style table
        for i in self.style_tree.get_children():
            self.style_tree.delete(i)
        # Determine categories present
        categories = sorted({tx.category for tx in self.state.transactions if tx.category})
        for cat in categories:
            style = self.state.category_styles.get(cat)
            colour = style.colour if style else ""
            self.style_tree.insert("", "end", iid=cat, values=(cat, colour or ""))

    def _refresh_summary(self) -> None:
        # Compute summary of expenses/income for current filters
        # Apply same filters as Sankey builder
        month = None if self.month_var.get() == "All" else self.month_var.get()
        owner_filter = None if self.owner_var.get() == "All" else self.owner_var.get()
        include_income = self.include_income.get()
        include_ignored = self.include_ignored.get()
        def should_include(tx: Transaction) -> bool:
            if not include_ignored and tx.ignored:
                return False
            if month is not None and not tx.date.strftime("%Y-%m").startswith(month):
                return False
            if owner_filter is not None and tx.owner != owner_filter:
                return False
            if not include_income and tx.amount > 0:
                return False
            return True
        filtered = [tx for tx in self.state.transactions if should_include(tx)]
        # Sum by (category, owner)
        totals: Dict[Tuple[str, str], float] = {}
        for tx in filtered:
            cat = tx.category or "Uncategorised"
            owner = tx.owner or "Unassigned"
            key = (cat, owner)
            totals[key] = totals.get(key, 0.0) + tx.amount
        # Compute share of expenses (negative amounts) for each category
        total_expenses = sum(-tx.amount for tx in filtered if tx.amount < 0)
        # Clear summary tree
        for i in self.summary_tree.get_children():
            self.summary_tree.delete(i)
        for (cat, owner), total in sorted(totals.items(), key=lambda x: (x[0][0], x[0][1])):
            # Compute share of expenses
            share = (abs(total) / total_expenses * 100.0) if total_expenses != 0 and total < 0 else 0.0
            self.summary_tree.insert(
                "",
                "end",
                values=(cat, owner, f"{total:.2f}", f"{share:.1f}%" if share else "")
            )

    # ------------------------------------------------------------------
    # Actions for data page
    def _import_csv(self) -> None:
        paths = filedialog.askopenfilenames(title="Select CSV files", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if not paths:
            return
        importer = TransactionImporter()
        new_txs: List[Transaction] = []
        for p in paths:
            try:
                txs = importer.import_csv(Path(p))
                new_txs.extend(txs)
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import {p}: {e}")
                return
        if new_txs:
            self.state = self.state.add_transactions(new_txs)
            self._refresh_all()

    def _export_state(self) -> None:
        path = filedialog.asksaveasfilename(title="Export state to JSON", defaultextension=".json", filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
        if not path:
            return
        try:
            save_state(self.state, Path(path))
            messagebox.showinfo("Export State", f"State saved to {path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save state: {e}")

    def _import_state(self) -> None:
        path = filedialog.askopenfilename(title="Import state from JSON", defaultextension=".json", filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
        if not path:
            return
        try:
            self.state = load_state(Path(path))
            self._refresh_all()
            messagebox.showinfo("Import State", f"State loaded from {path}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to load state: {e}")

    def _clear_state(self) -> None:
        if messagebox.askyesno("Clear all data", "This will remove all transactions and rules. Continue?"):
            self.state = self.state.clear()
            self._refresh_all()

    # Rules operations
    def _add_rule_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Rule")
        ttk.Label(dialog, text="Pattern:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        pattern_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=pattern_var).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Category:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        category_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=category_var).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Owner:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        owner_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=owner_var).grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Priority (integer):").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        priority_var = tk.StringVar(value="0")
        ttk.Entry(dialog, textvariable=priority_var).grid(row=3, column=1, padx=5, pady=5)
        def on_save() -> None:
            try:
                pattern = pattern_var.get().strip()
                category = category_var.get().strip()
                owner = owner_var.get().strip()
                priority = int(priority_var.get()) if priority_var.get().strip() else 0
                if not pattern:
                    messagebox.showwarning("Add Rule", "Pattern cannot be empty")
                    return
                rule_id = _generate_id(pattern, category, owner, str(priority))
                new_rule = Rule(id=rule_id, pattern=pattern, category=category, owner=owner, priority=priority)
                self.state = self.state.add_rule(new_rule)
                dialog.destroy()
                self._refresh_all()
            except ValueError:
                messagebox.showwarning("Add Rule", "Priority must be an integer")
        ttk.Button(dialog, text="Save", command=on_save).grid(row=4, column=0, columnspan=2, pady=10)

    def _delete_selected_rule(self) -> None:
        selected = self.rule_tree.selection()
        if not selected:
            return
        rule_id = selected[0]
        if messagebox.askyesno("Delete Rule", "Delete the selected rule?"):
            self.state = self.state.remove_rule(rule_id)
            self._refresh_all()

    # Review editing
    def _edit_selected_unclassified(self) -> None:
        selected = self.review_tree.selection()
        if not selected:
            messagebox.showinfo("Edit Transaction", "Please select a transaction to edit")
            return
        self._open_edit_dialog(selected[0])

    def _on_edit_unclassified(self, event: tk.Event) -> None:
        item_id = self.review_tree.identify_row(event.y)
        if item_id:
            self._open_edit_dialog(item_id)

    def _open_edit_dialog(self, tx_id: str) -> None:
        # Find transaction
        tx = next((t for t in self.state.transactions if t.id == tx_id), None)
        if not tx:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Transaction")
        ttk.Label(dialog, text=f"Description: {tx.description}").grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        ttk.Label(dialog, text=f"Amount: {tx.amount:.2f} {tx.currency}").grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        # Category entry
        ttk.Label(dialog, text="Category:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        cat_var = tk.StringVar(value=tx.category or "")
        ttk.Entry(dialog, textvariable=cat_var).grid(row=2, column=1, padx=5, pady=5)
        # Owner entry
        ttk.Label(dialog, text="Owner:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        owner_var = tk.StringVar(value=tx.owner or "")
        ttk.Entry(dialog, textvariable=owner_var).grid(row=3, column=1, padx=5, pady=5)
        # Create rule checkbox
        create_rule_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="Save as rule", variable=create_rule_var).grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        def on_save() -> None:
            category = cat_var.get().strip() or None
            owner = owner_var.get().strip() or None
            # Update transaction assignment
            self.state = self.state.update_transaction(tx_id, category, owner)
            if create_rule_var.get() and tx.description.strip():
                # Derive a pattern suggestion: take first word in lower case
                pattern = tx.description.lower().split()[0]
                # Remove non‑alphanumeric characters from pattern
                pattern = ''.join(ch for ch in pattern if ch.isalnum())
                if pattern:
                    rule_id = _generate_id(pattern, category or "", owner or "")
                    new_rule = Rule(id=rule_id, pattern=pattern, category=category or "", owner=owner or "", priority=0)
                    self.state = self.state.add_rule(new_rule)
            dialog.destroy()
            self._refresh_all()
        ttk.Button(dialog, text="Save", command=on_save).grid(row=5, column=0, columnspan=2, pady=10)

    # ------------------------------------------------------------------
    # Visualisation actions
    def _on_filter_change(self) -> None:
        self._refresh_summary()

    def _open_sankey(self) -> None:
        # Determine filters
        month = None if self.month_var.get() == "All" else self.month_var.get()
        owner_filter = None if self.owner_var.get() == "All" else self.owner_var.get()
        # Build figure
        fig = self.sankey_builder.build(
            transactions=self.state.transactions,
            styles=self.state.category_styles,
            month=month,
            owner_filter=owner_filter,
            include_income=self.include_income.get(),
            include_ignored=self.include_ignored.get(),
        )
        # Save to temporary HTML file and open in browser
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, "budget_sankey.html")
        fig.write_html(tmp_path, include_plotlyjs="cdn")
        webbrowser.open(f"file://{tmp_path}")

    def _change_category_colour(self) -> None:
        selected = self.style_tree.selection()
        if not selected:
            messagebox.showinfo("Change Colour", "Please select a category")
            return
        category = selected[0]
        current_colour = self.state.category_styles.get(category).colour if category in self.state.category_styles else None
        # Ask user to pick a new colour
        rgb, colour_hex = colorchooser.askcolor(title=f"Select colour for {category}", initialcolor=current_colour)
        if colour_hex:
            self.state = self.state.set_category_colour(category, colour_hex)
            self._refresh_styles()
            self._refresh_summary()


def run_app() -> None:
    root = tk.Tk()
    # Use themed ttk style if available
    try:
        from tkinter import ttk as ttk_module
        style = ttk_module.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    app = BudgetApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_app()