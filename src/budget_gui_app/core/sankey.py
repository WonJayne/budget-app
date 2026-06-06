"""Build Plotly Sankey figures from current transaction state."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

import plotly.graph_objects as go

from .models import CategoryStyle, Transaction

DEFAULT_NODE_COLOUR = "#9ca3af"
DEFAULT_LINK_COLOUR = "rgba(156, 163, 175, 0.35)"


class SankeyBuilder:
    def build(
        self,
        transactions: Iterable[Transaction],
        styles: Mapping[str, CategoryStyle],
        *,
        month: str | None,
        owner: str | None,
        currency: str | None,
        include_income: bool,
        include_ignored: bool,
    ) -> go.Figure:
        filtered = [
            transaction
            for transaction in transactions
            if self._included(transaction, month, owner, currency, include_income, include_ignored)
        ]

        node_index: dict[str, int] = {}
        labels: list[str] = []
        colours: list[str] = []

        def node(label: str) -> int:
            if label not in node_index:
                node_index[label] = len(labels)
                labels.append(label)
                colours.append(styles.get(label, CategoryStyle(label)).colour or DEFAULT_NODE_COLOUR)
            return node_index[label]

        flows: defaultdict[tuple[int, int], float] = defaultdict(float)
        for transaction in filtered:
            if transaction.amount > 0:
                source = "Income"
                target = transaction.owner or "Unassigned"
                value = transaction.amount
            else:
                source = transaction.owner or "Unassigned"
                target = transaction.category or "Uncategorised"
                value = abs(transaction.amount)
            flows[(node(source), node(target))] += value

        sources = [source for source, _ in flows]
        targets = [target for _, target in flows]
        values = [value for value in flows.values()]
        link_colours = [colours[target] if colours[target] != DEFAULT_NODE_COLOUR else DEFAULT_LINK_COLOUR for target in targets]

        fig = go.Figure(
            go.Sankey(
                arrangement="snap",
                node={"label": labels, "color": colours, "pad": 12, "thickness": 16},
                link={"source": sources, "target": targets, "value": values, "color": link_colours},
            )
        )
        fig.update_layout(title_text="Household Budget Sankey", font={"size": 12}, margin={"l": 8, "r": 8, "t": 36, "b": 8})
        return fig

    @staticmethod
    def _included(
        transaction: Transaction,
        month: str | None,
        owner: str | None,
        currency: str | None,
        include_income: bool,
        include_ignored: bool,
    ) -> bool:
        if not include_ignored and transaction.ignored:
            return False
        if month and transaction.date.strftime("%Y-%m") != month:
            return False
        if owner and transaction.owner != owner:
            return False
        if currency and transaction.currency != currency:
            return False
        if not include_income and transaction.amount > 0:
            return False
        return True
