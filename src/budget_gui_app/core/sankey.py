"""Sankey diagram construction for the budget GUI application.

This module defines a builder for converting a set of classified
transactions into a Plotly Sankey diagram.  Transactions can be
filtered by month and owner, and category colours are drawn from the
application’s style configuration.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable, Mapping, Optional, Tuple

import plotly.graph_objects as go

from .models import CategoryStyle, Transaction


class SankeyBuilder:
    """Build interactive Sankey diagrams from transactions."""

    def build(
        self,
        transactions: Iterable[Transaction],
        styles: Mapping[str, CategoryStyle],
        month: Optional[str] = None,
        owner_filter: Optional[str] = None,
        include_income: bool = True,
        include_ignored: bool = False,
    ) -> go.Figure:
        """Create a Plotly Sankey figure from the provided transactions.

        Args:
            transactions: Classified transactions to visualise.
            styles: Mapping of category to styling information.
            month: Optional ``YYYY-MM`` filter.  Only transactions
                whose date begins with this prefix are included.
            owner_filter: Optional owner filter.  ``None`` means all
                owners.  ``"shared"`` or an individual's name will
                include only transactions for that owner.  Note that
                income transactions assigned to other owners will be
                excluded.
            include_income: Whether to include positive transactions.
            include_ignored: Whether to include ignored transactions.

        Returns:
            A Plotly ``Figure`` representing the Sankey diagram.
        """
        # Filter transactions by month and owner
        def should_include(tx: Transaction) -> bool:
            if not include_ignored and tx.ignored:
                return False
            if month is not None:
                if not tx.date.strftime("%Y-%m").startswith(month):
                    return False
            if owner_filter and owner_filter != tx.owner:
                # For positive amounts (income) owner may be None; treat as unassigned
                return False
            if not include_income and tx.amount > 0:
                return False
            return True

        filtered = [tx for tx in transactions if should_include(tx)]

        # Build flows: income flows from 'Income' to owner; expenses flow from owner to category
        flows = []  # list of (source_label, target_label, value)
        for tx in filtered:
            if tx.amount > 0:
                source = "Income"
                target = tx.owner or "Unassigned"
                value = tx.amount
            else:
                source = tx.owner or "Unassigned"
                target = tx.category or "Uncategorised"
                value = abs(tx.amount)
            flows.append((source, target, value))

        # Build unique nodes and assign colours
        node_index: dict[str, int] = {}
        labels: list[str] = []
        colours: list[Optional[str]] = []

        def get_node(name: str) -> int:
            if name not in node_index:
                node_index[name] = len(labels)
                labels.append(name)
                # Determine colour: use category style when target is a category
                if name in styles and styles[name].colour:
                    colours.append(styles[name].colour)
                else:
                    colours.append(None)
            return node_index[name]

        # Aggregate flows by (source, target)
        aggregated: defaultdict[Tuple[int, int], float] = defaultdict(float)
        for src, tgt, val in flows:
            src_idx = get_node(src)
            tgt_idx = get_node(tgt)
            aggregated[(src_idx, tgt_idx)] += val

        sources: list[int] = []
        targets: list[int] = []
        values: list[float] = []
        link_colours: list[Optional[str]] = []
        for (src_idx, tgt_idx), val in aggregated.items():
            sources.append(src_idx)
            targets.append(tgt_idx)
            values.append(val)
            # Inherit colour from target if defined
            colour = colours[tgt_idx] if tgt_idx < len(colours) else None
            link_colours.append(colour)

        node_dict = {"label": labels}
        if any(colours):
            node_dict["color"] = colours
        link_dict = {"source": sources, "target": targets, "value": values}
        if any(link_colours):
            link_dict["color"] = link_colours

        fig = go.Figure(
            go.Sankey(
                arrangement="snap",
                node=node_dict,
                link=link_dict,
            )
        )
        fig.update_layout(
            title_text="Household Budget Sankey", font=dict(size=12), margin=dict(l=5, r=5, t=30, b=5)
        )
        return fig